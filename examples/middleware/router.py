"""
Example of how you can implement explicit routes using middleware.
For a comprehensive example of this (with route decorators and type
checking see the `rest` example at 
https://github.com/patx/micropie/tree/main/examples/rest
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from MicroPie import App, HttpMiddleware, Request

class ExplicitRouter(HttpMiddleware):
    def __init__(self):
        # Map route paths to (method, regex pattern, handler name)
        self.routes: Dict[str, Tuple[str, str, str]] = {}
    
    def add_route(self, path: str, handler_name: str, method: str = "GET") -> None:
        """
        Register an explicit route with its handler method name and HTTP method.
        
        Args:
            path: The route pattern (e.g., "/api/users/{user}/records/{record}")
            handler_name: The handler method name (e.g., "api")
            method: The HTTP method (e.g., "GET", "POST")
        """
        pattern = re.sub(r"{([^}]+)}", r"([^/]+)", path)
        pattern = f"^{pattern}$"
        self.routes[path] = (method, pattern, handler_name)
    
    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Match the request path and set path parameters for MicroPie routing.
        
        Args:
            request: The MicroPie Request object
        
        Returns:
            None to let MicroPie handle parsing and routing
        """
        path = request.scope["path"]
        
        for route_path, (method, pattern, handler_name) in self.routes.items():
            if request.method != method:
                continue
            match = re.match(pattern, path)
            if match:
                # Ensure path parameters are strings
                request.path_params = [str(param) for param in match.groups()]
                request._route_handler = handler_name
                return None
        
        return None
    
    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        return None


class MyApp(App):
    def __init__(self):
        super().__init__()
        self.router = ExplicitRouter()
        self.middlewares.append(self.router)
        
        # Register explicit routes
        self.router.add_route("/api/users/{user}/records/{record}", "_get_record", "GET")
        self.router.add_route("/api/users/{user}/records", "_create_record", "POST")
        self.router.add_route("/api/users/{user}/records/{record}/details/subdetails", "_get_record_subdetails", "GET")
    
    async def _get_record(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id}
        except ValueError:
            return {"error": "Record must be an integer"}
    
    async def _create_record(self, user: str):
        try:
            data = self.request.get_json
            return {"user": user, "record": data.get("record_id"), "created": True}
        except Exception as e:
            return {"error": f"Invalid JSON: {str(e)}"}
    
    async def _get_record_subdetails(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id, "subdetails": "more detailed info"}
        except ValueError:
            return {"error": "Record must be an integer"}
    
    # Implicitly routed
    async def records(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id, "implicit": True}
        except ValueError:
            return {"error": "Record must be an integer"}

    # Private route, not exposed in any way
    async def _private(self):
        return {"viewing": "private"}

app = MyApp()
