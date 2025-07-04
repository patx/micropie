import re
from typing import Dict, List, Optional, Tuple, Any, Callable, Type, Union
import uuid
from micropie import App, HttpMiddleware, WebSocketMiddleware, Request, WebSocketRequest

# Specific exceptions for better error handling
class RouteError(Exception):
    """Base exception for routing errors."""
    pass

class InvalidPathError(RouteError):
    """Raised for invalid route path formats."""
    pass

class UnsupportedTypeError(RouteError):
    """Raised for unsupported parameter types."""
    pass

class InvalidMethodError(RouteError):
    """Raised for invalid HTTP methods."""
    pass

class BaseRouter:
    """Base class for HTTP and WebSocket routers to share logic."""
    def __init__(self):
        # Map route paths to (methods/subprotocol, compiled regex, handler, param_types)
        self.routes: Dict[str, Tuple[Any, re.Pattern, Callable, List[Type]]] = {}
        self._param_types = {
            "int": (int, r"(\d+)"),
            "str": (str, r"([^/]+)"),
            "float": (float, r"([-+]?\d*\.?\d+)"),
            "uuid": (uuid.UUID, r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
        }

    def _process_param(self, match: re.Match, param_types: List[Type]) -> str:
        """Process a route parameter and store its type."""
        param_name = match.group(1)
        param_type_str = match.group(2) or "str"  # Default to str if no type specified
        if param_type_str not in self._param_types:
            raise UnsupportedTypeError(f"Unsupported parameter type: {param_type_str}")
        param_type, regex = self._param_types[param_type_str]
        param_types.append(param_type)
        return regex

    def add_route(self, path: str, handler: Callable, methods_or_subprotocol: Any) -> None:
        """
        Register a route with its handler and methods/subprotocol.
        
        Args:
            path: The route pattern (e.g., "/users/{user}/{record:int}")
            handler: The handler function
            methods_or_subprotocol: List of HTTP methods or WebSocket subprotocol
        """
        if not path.startswith("/"):
            raise InvalidPathError(f"Route path must start with '/': {path}")
        param_types = []
        # Support both {name} and {name:type} syntax
        pattern = re.sub(r"{([^:}]*)?(?::([^}]+))?}", lambda m: self._process_param(m, param_types), path)
        try:
            compiled_pattern = re.compile(f"^{pattern}$")
        except re.error as e:
            raise InvalidPathError(f"Invalid route pattern: {path} ({str(e)})")
        self.routes[path] = (methods_or_subprotocol, compiled_pattern, handler, param_types)

    def list_routes(self) -> List[Dict[str, Any]]:
        """
        Return a list of registered routes for debugging.
        
        Returns:
            List of dictionaries containing route details.
        """
        return [
            {"path": path, "methods_or_subprotocol": details[0], "handler": details[2].__name__}
            for path, details in self.routes.items()
        ]

class ExplicitRouter(HttpMiddleware):
    """Middleware for explicit HTTP routing with type-safe parameters."""
    def __init__(self):
        super().__init__()
        self.router = BaseRouter()

    def add_route(self, path: str, handler: Callable, methods: List[str]) -> None:
        """
        Register an explicit HTTP route.
        
        Args:
            path: The route pattern (e.g., "/users/{user}/{record:int}")
            handler: The handler function
            methods: List of HTTP methods (e.g., ["GET", "POST"])
        """
        if not methods:
            raise InvalidMethodError("At least one HTTP method must be specified")
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        methods = [m.upper() for m in methods]
        if not all(m in valid_methods for m in methods):
            raise InvalidMethodError(f"Invalid HTTP methods: {', '.join(set(methods) - valid_methods)}")
        self.router.add_route(path, handler, methods)

    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Match the request path and set path parameters.
        
        Args:
            request: The MicroPie Request object
        
        Returns:
            Dictionary with response details to short-circuit, or None to continue.
        """
        path = request.scope["path"]
        for route_path, (methods, pattern, handler, param_types) in self.router.routes.items():
            if request.method not in methods:
                continue
            match = pattern.match(path)
            if match:
                try:
                    params = [
                        param_type(param) for param, param_type in zip(match.groups(), param_types)
                    ]
                    request.path_params = params
                    request._route_handler = handler.__name__
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
    """Middleware for explicit WebSocket routing with type-safe parameters."""
    def __init__(self):
        super().__init__()
        self.router = BaseRouter()

    def add_route(self, path: str, handler: Callable, subprotocol: Optional[str] = None) -> None:
        """
        Register an explicit WebSocket route.
        
        Args:
            path: The route pattern (e.g., "/ws/users/{user}/chat")
            handler: The handler function
            subprotocol: Optional WebSocket subprotocol
        """
        self.router.add_route(path, handler, subprotocol)

    async def before_websocket(self, request: WebSocketRequest) -> Optional[Dict]:
        """
        Match the WebSocket path and set path parameters.
        
        Args:
            request: The WebSocketRequest object
        
        Returns:
            Dictionary with close details to reject, or None to continue.
        """
        path = request.scope["path"]
        for route_path, (subprotocol, pattern, handler, param_types) in self.router.routes.items():
            match = pattern.match(path)
            if match:
                try:
                    params = [
                        param_type(param) for param, param_type in zip(match.groups(), param_types)
                    ]
                    request.path_params = params
                    request._ws_route_handler = handler.__name__
                    request._ws_subprotocol = subprotocol
                    return None
                except ValueError as e:
                    return {"code": 1008, "reason": f"Invalid parameter format: {str(e)}"}
        return None

    async def after_websocket(self, request: WebSocketRequest) -> None:
        """Log WebSocket session closure for debugging."""
        print(f"WebSocket session closed for path: {request.scope['path']}")

def route(path: str, method: Union[str, List[str]] = "GET"):
    """
    Decorator to register an HTTP route with validation.
    
    Args:
        path: The route path (e.g., "/users/{user}")
        method: HTTP method(s) as a string or list
    
    Raises:
        InvalidMethodError: If invalid HTTP methods are provided
        InvalidPathError: If the path format is invalid
    """
    def decorator(handler: Callable) -> Callable:
        methods = [method] if isinstance(method, str) else method
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        methods = [m.upper() for m in methods]
        if not all(m in valid_methods for m in methods):
            raise InvalidMethodError(f"Invalid HTTP methods: {', '.join(set(methods) - valid_methods)}")
        if not path.startswith("/"):
            raise InvalidPathError(f"Route path must start with '/': {path}")
        handler._route = (path, methods)
        return handler
    return decorator

def ws_route(path: str, subprotocol: Optional[str] = None):
    """
    Decorator to register a WebSocket route with optional subprotocol.
    
    Args:
        path: The WebSocket route path (e.g., "/ws/chat/{room}")
        subprotocol: Optional WebSocket subprotocol
    
    Raises:
        InvalidPathError: If the path format is invalid
    """
    def decorator(handler: Callable) -> Callable:
        if not path.startswith("/"):
            raise InvalidPathError(f"Route path must start with '/': {path}")
        handler._ws_route = (path, subprotocol)
        return handler
    return decorator

class ExplicitApp(App):
    """A MicroPie App subclass with explicit routing support."""
    def __init__(self, session_backend=None):
        super().__init__(session_backend=session_backend)
        self.router = ExplicitRouter()
        self.ws_router = WebSocketExplicitRouter()
        self.middlewares.append(self.router)
        self.ws_middlewares.append(self.ws_router)
        self._register_routes()

    def _register_routes(self):
        """Register HTTP and WebSocket routes from decorated methods."""
        for name, method in self.__class__.__dict__.items():
            if hasattr(method, "_route"):
                path, methods = method._route
                self.router.add_route(path, getattr(self, name), methods)
            if hasattr(method, "_ws_route"):
                path, subprotocol = method._ws_route
                self.ws_router.add_route(path, getattr(self, name), subprotocol)

    def list_routes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return all registered HTTP and WebSocket routes for debugging.
        
        Returns:
            Dictionary with 'http' and 'websocket' keys containing route details.
        """
        return {
            "http": self.router.router.list_routes(),
            "websocket": self.ws_router.router.list_routes()
        }
