import re
import inspect
import json
from typing import Callable, Dict, List, Optional, Tuple, Any
from MicroPie import App, HttpMiddleware, Request

class ExplicitRoutingMiddleware(HttpMiddleware):
    def __init__(self):
        # Registry to map route patterns to handler callables and HTTP methods
        self.routes: Dict[str, Tuple[Callable, str, str]] = {}
    
    def add_route(self, path: str, handler: Callable, method: str = "GET") -> None:
        """
        Register an explicit route with its handler callable and HTTP method.
        
        Args:
            path: The route pattern (e.g., "/api/users/{user}/records/{record}")
            handler: The handler method callable (e.g., app.get_record)
            method: The HTTP method (e.g., "GET", "POST")
        """
        # Convert path pattern to regex (e.g., "/api/users/{user}/records/{record}" -> "^/api/users/([^/]+)/records/([^/]+)$")
        pattern = re.sub(r"{([^}]+)}", r"([^/]+)", path)
        pattern = f"^{pattern}$"
        self.routes[path] = (handler, method, pattern)
    
    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Match the request path against registered routes and dispatch to the handler.
        
        Args:
            request: The MicroPie Request object
        
        Returns:
            Optional response dict if handled, None to continue to implicit routing
        """
        path = request.scope["path"]
        request_method = request.method
        
        for route_path, (handler, method, pattern) in self.routes.items():
            if method != request_method:
                continue
            match = re.match(pattern, path)
            if match:
                # Extract path parameters
                path_params = list(match.groups())
                
                # Build arguments based on handler signature
                sig = inspect.signature(handler)
                func_args = []
                path_params_copy = path_params[:]
                for param in sig.parameters.values():
                    if param.name == "self":
                        continue
                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        func_args.extend(path_params_copy)
                        path_params_copy = []
                        continue
                    if path_params_copy:
                        func_args.append(path_params_copy.pop(0))
                    elif param.default is not param.empty:
                        func_args.append(param.default)
                    else:
                        return {
                            "status_code": 400,
                            "body": f"400 Bad Request: Missing required parameter '{param.name}'",
                            "headers": []
                        }
                
                try:
                    # Call handler with path parameters
                    result = await handler(*func_args) if inspect.iscoroutinefunction(handler) else handler(*func_args)
                    status_code = 200
                    response_body = result
                    extra_headers = []
                    
                    # Handle tuple response (body, status_code, headers)
                    if isinstance(result, tuple):
                        status_code, response_body = result[0], result[1]
                        extra_headers = result[2] if len(result) > 2 else []
                    
                    # Convert dict/list to JSON if needed
                    if isinstance(response_body, (dict, list)):
                        response_body = json.dumps(response_body)
                        extra_headers.append(("Content-Type", "application/json"))
                    
                    return {
                        "status_code": status_code,
                        "body": response_body,
                        "headers": extra_headers
                    }
                except Exception as e:
                    print(f"Handler error: {e}")
                    return {
                        "status_code": 500,
                        "body": "500 Internal Server Error",
                        "headers": []
                    }
        
        # No matching explicit route, proceed to implicit routing
        return None
    
    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        """
        Pass through the response unchanged.
        
        Args:
            request: The MicroPie Request object
            status_code: HTTP status code
            response_body: Response body
            extra_headers: List of response headers
        
        Returns:
            None to pass through the response unchanged
        """
        return None

# Example usage
class MyApp(App):
    def __init__(self):
        super().__init__()
        self.router = ExplicitRoutingMiddleware()
        self.middlewares.append(self.router)
        
        # Register explicit routes
        self.router.add_route("/api/users/{user}/records/{record}", self.get_record, "GET")
        self.router.add_route("/api/users/{user}/records", self.create_record, "POST")
        self.router.add_route("/api/users/{user}/records/{record}/details/subdetails", self.get_record_subdetails, "GET")
        # Implicit route handled by MicroPie's default routing
        # Note: /records/{user}/{record} will use implicit routing since not explicitly defined
    
    async def get_record(self, user: str, record: str):
        try:
            record_id = int(record)
            # Access request via self.request if needed
            return {"user": user, "record": record_id}
        except ValueError:
            return {"error": "Record must be an integer"}, 400
    
    async def create_record(self, user: str):
        data = self.request.get_json
        return {"user": user, "record": data.get("record_id"), "created": True}, 201
    
    async def get_record_subdetails(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id, "subdetails": "more detailed info"}
        except ValueError:
            return {"error": "Record must be an integer"}, 400
    
    async def records(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id, "implicit": True}
        except ValueError:
            return {"error": "Record must be an integer"}, 400

app = MyApp()
