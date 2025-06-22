"""
Example of a WebSocket middleware for MicroPie that handles WebSocket connections.

This middleware enables WebSocket support by intercepting WebSocket requests,
managing the connection lifecycle, and routing messages to appropriate handlers.
It includes a specialized WebSocketRequest class to handle WebSocket scopes.

For comprehensive WebSocket examples, refer to the MicroPie documentation at
https://patx.github.io/micropie
"""

import re
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Awaitable
from MicroPie import App, HttpMiddleware, Request, current_request
from urllib.parse import parse_qs

class WebSocketRequest:
    """Represents a WebSocket request in the MicroPie framework."""
    def __init__(self, scope: Dict[str, Any]) -> None:
        """
        Initialize a new WebSocketRequest instance.

        Args:
            scope: The ASGI scope dictionary for the WebSocket request.
        """
        self.scope: Dict[str, Any] = scope
        self.path_params: List[str] = []
        self.query_params: Dict[str, List[str]] = {}
        self.session: Dict[str, Any] = {}
        self.headers: Dict[str, str] = {
            k.decode("utf-8", errors="replace").lower(): v.decode("utf-8", errors="replace")
            for k, v in scope.get("headers", [])
        }
        # Parse query parameters
        self.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))

class WebSocketMiddleware(HttpMiddleware):
    def __init__(self):
        # Map WebSocket paths to handler method names
        self.ws_routes: Dict[str, Tuple[str, str]] = {}
    
    def add_ws_route(self, path: str, handler_name: str) -> None:
        """
        Register a WebSocket route with its handler method name.
        
        Args:
            path: The WebSocket route pattern (e.g., "/ws/chat/{room}")
            handler_name: The handler method name (e.g., "_handle_chat")
        """
        pattern = re.sub(r"{([^}]+)}", r"([^/]+)", path)
        pattern = f"^{pattern}$"
        self.ws_routes[path] = (pattern, handler_name)
    
    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Skip WebSocket requests in the HTTP middleware pipeline.
        
        Args:
            request: The MicroPie Request object
        
        Returns:
            None to let MicroPie handle requests
        """
        if request.scope["type"] == "websocket":
            return None  # WebSocket requests are handled in _handle_websocket
        return None

    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        return None

class WebSocketApp(App):
    def __init__(self):
        super().__init__()
        self.ws_middleware = WebSocketMiddleware()
        self.middlewares.append(self.ws_middleware)
        
        # Register WebSocket routes
        self.ws_middleware.add_ws_route("/ws/chat/{room}", "_handle_chat")
        self.ws_middleware.add_ws_route("/ws/notifications", "_handle_notifications")
    
    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Override the App's ASGI callable to handle WebSocket connections.
        """
        if scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)
    
    async def _handle_websocket(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Handle WebSocket connections by routing to the appropriate handler.
        
        Args:
            scope: The ASGI scope dictionary
            receive: The callable to receive ASGI events
            send: The callable to send ASGI events
        """
        request = WebSocketRequest(scope)
        token = current_request.set(request)
        
        try:
            # Perform WebSocket route matching
            path = scope["path"]
            handler = None
            path_params = []
            for route_path, (pattern, handler_name) in self.ws_middleware.ws_routes.items():
                match = re.match(pattern, path)
                if match:
                    path_params = [str(param) for param in match.groups()]
                    handler = getattr(self, handler_name, None)
                    break
            
            if not handler:
                await send({
                    "type": "websocket.close",
                    "code": 1008,  # Policy violation
                    "reason": "No matching WebSocket route"
                })
                return
            
            # Accept the WebSocket connection
            await send({
                "type": "websocket.accept",
                "subprotocol": None,
            })
            
            # Execute the WebSocket handler with path parameters
            try:
                await handler(request, receive, send, *path_params)
            except Exception as e:
                print(f"WebSocket error: {e}")
                await send({
                    "type": "websocket.close",
                    "code": 1011,  # Internal error
                    "reason": f"Handler error: {str(e)}"
                })
        
        finally:
            current_request.reset(token)
    
    async def _handle_chat(self, request: WebSocketRequest, receive: Callable, send: Callable, room: str):
        """
        Handle WebSocket connections for a chat room.
        
        Args:
            request: The WebSocketRequest object
            receive: The ASGI receive callable
            send: The ASGI send callable
            room: The chat room identifier from the path
        """
        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                break
            if message["type"] == "websocket.receive":
                data = message.get("text") or message.get("bytes", b"").decode("utf-8", "ignore")
                response = json.dumps({"room": room, "message": data, "type": "chat.message"})
                await send({
                    "type": "websocket.send",
                    "text": response
                })
    
    async def _handle_notifications(self, request: WebSocketRequest, receive: Callable, send: Callable):
        """
        Handle WebSocket connections for sending notifications.
        
        Args:
            request: The WebSocketRequest object
            receive: The ASGI receive callable
            send: The ASGI send callable
        """
        try:
            count = 0
            while True:
                await asyncio.sleep(5)  # Send notification every 5 seconds
                response = json.dumps({"notification": f"Update #{count}", "type": "notification"})
                await send({
                    "type": "websocket.send",
                    "text": response
                })
                count += 1
        except asyncio.CancelledError:
            await send({
                "type": "websocket.close",
                "code": 1000,  # Normal closure
            })

app = WebSocketApp()
