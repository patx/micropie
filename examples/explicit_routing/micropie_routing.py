import re
from typing import Dict, List, Optional, Tuple, Any, Callable, Type, Union
from MicroPie import App, HttpMiddleware, WebSocketMiddleware, Request, WebSocketRequest

class RouteError(Exception):
    """Custom exception for route-related errors."""
    pass

class ExplicitRouter(HttpMiddleware):
    def __init__(self):
        # Map route paths to (methods, regex pattern, handler_name, param_types)
        self.routes: Dict[str, Tuple[List[str], str, str, List[Type]]] = {}
    
    def add_route(self, path: str, handler: Callable, methods: List[str]) -> None:
        """
        Register an explicit route with its handler and HTTP methods.
        
        Args:
            path: The route pattern (e.g., "/api/users/{user:str}/records/{record:int}")
            handler: The handler function
            methods: List of HTTP methods (e.g., ["GET", "POST"])
        """
        if not methods:
            raise RouteError("At least one HTTP method must be specified")
        # Normalize methods to uppercase
        methods = [m.upper() for m in methods]
        # Parse parameter types from path
        param_types = []
        pattern = re.sub(r"{([^:]+):([^}]+)}", lambda m: self._process_param(m, param_types), path)
        pattern = f"^{pattern}$"
        # Store handler name instead of handler function
        self.routes[path] = (methods, pattern, handler.__name__, param_types)
    
    def _process_param(self, match: re.Match, param_types: List[Type]) -> str:
        """Process a route parameter and store its type."""
        param_name, param_type = match.group(1), match.group(2)
        if param_type == "int":
            param_types.append(int)
            return r"(\d+)"
        elif param_type == "str":
            param_types.append(str)
            return r"([^/]+)"
        else:
            raise RouteError(f"Unsupported parameter type: {param_type}")
    
    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Match the request path and set path parameters for MicroPie routing.
        
        Args:
            request: The MicroPie Request object
        
        Returns:
            Dictionary with response details to short-circuit, or None to continue.
        """
        path = request.scope["path"]
        
        for route_path, (methods, pattern, handler_name, param_types) in self.routes.items():
            if request.method not in methods:
                continue
            match = re.match(pattern, path)
            if match:
                try:
                    # Convert parameters to their specified types
                    params = [
                        param_type(param) for param, param_type in zip(match.groups(), param_types)
                    ]
                    request.path_params = params
                    request._route_handler = handler_name  # Set handler name as string
                    return None
                except ValueError as e:
                    return {"status_code": 400, "body": f"Invalid parameter format: {str(e)}"}
        
        return None
    
    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        return None

class WebSocketExplicitRouter(WebSocketMiddleware):
    def __init__(self):
        # Map WebSocket route paths to (regex pattern, handler_name, param_types)
        self.routes: Dict[str, Tuple[str, str, List[Type]]] = {}
    
    def add_route(self, path: str, handler: Callable) -> None:
        """
        Register an explicit WebSocket route with its handler.
        
        Args:
            path: The route pattern (e.g., "/ws/users/{user:str}/chat")
            handler: The handler function
        """
        # Parse parameter types from path
        param_types = []
        pattern = re.sub(r"{([^:]+):([^}]+)}", lambda m: self._process_param(m, param_types), path)
        pattern = f"^{pattern}$"
        # Store handler name instead of handler function
        self.routes[path] = (pattern, handler.__name__, param_types)
    
    def _process_param(self, match: re.Match, param_types: List[Type]) -> str:
        """Process a route parameter and store its type."""
        param_name, param_type = match.group(1), match.group(2)
        if param_type == "int":
            param_types.append(int)
            return r"(\d+)"
        elif param_type == "str":
            param_types.append(str)
            return r"([^/]+)"
        else:
            raise RouteError(f"Unsupported parameter type: {param_type}")
    
    async def before_websocket(self, request: WebSocketRequest) -> Optional[Dict]:
        """
        Match the WebSocket path and set path parameters for routing.
        
        Args:
            request: The WebSocketRequest object
        
        Returns:
            Dictionary with close details to reject, or None to continue.
        """
        path = request.scope["path"]
        
        for route_path, (pattern, handler_name, param_types) in self.routes.items():
            match = re.match(pattern, path)
            if match:
                try:
                    # Convert parameters to their specified types
                    params = [
                        param_type(param) for param, param_type in zip(match.groups(), param_types)
                    ]
                    request.path_params = params
                    request._ws_route_handler = handler_name  # Set handler name as string
                    return None
                except ValueError as e:
                    return {"code": 1008, "reason": f"Invalid parameter format: {str(e)}"}
        
        return None
    
    async def after_websocket(self, request: WebSocketRequest) -> None:
        """Post-processing after WebSocket handler execution."""
        pass

def route(path: str, method: Union[str, List[str]] = "GET"):
    """Decorator to register a route for an HTTP handler method."""
    def decorator(handler: Callable) -> Callable:
        # Normalize method to a list
        methods = [method] if isinstance(method, str) else method
        handler._route = (path, methods)
        return handler
    return decorator

def ws_route(path: str):
    """Decorator to register a route for a WebSocket handler method."""
    def decorator(handler: Callable) -> Callable:
        handler._ws_route = path
        return handler
    return decorator

class ExplicitApp(App):
    """A subclass of MicroPie.App that automatically registers HTTP and WebSocket routes."""
    def __init__(self):
        super().__init__()
        self.router = ExplicitRouter()
        self.ws_router = WebSocketExplicitRouter()
        self.middlewares.append(self.router)
        self.ws_middlewares.append(self.ws_router)
        self._register_routes()
    
    def _register_routes(self):
        """Automatically register HTTP and WebSocket routes from decorated methods."""
        for name, method in self.__class__.__dict__.items():
            if hasattr(method, "_route"):
                path, methods = method._route
                self.router.add_route(path, getattr(self, name), methods)
            if hasattr(method, "_ws_route"):
                path = method._ws_route
                self.ws_router.add_route(path, getattr(self, name))
