"""
MicroPie: An ultra micro ASGI web framework.

MicroPie is designed for lightweight web applications, offering 
a minimalistic API for building ASGI-compatible web services. 
It prioritizes simplicity and performance.

Homepage and documentation: https://patx.github.io/micropie

Copyright (c) 2025, Harrison Erd.
License: BSD3 (see LICENSE for details)
"""

__author__ = 'Harrison Erd'
__license__ = 'BSD3'

import asyncio
import contextvars
import inspect
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

try:
    import orjson as json  # Use `orjson` if installed as it is faster
except ImportError:
    import json

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_INSTALLED = True
except ImportError:
    JINJA_INSTALLED = False

try:
    from multipart import PushMultipartParser, MultipartSegment
    MULTIPART_INSTALLED = True
except ImportError:
    MULTIPART_INSTALLED = False


# -----------------------------
# Session Backend Abstraction
# -----------------------------
SESSION_TIMEOUT: int = 8 * 3600  # Default 8 hours

class SessionBackend(ABC):
    @abstractmethod
    async def load(self, session_id: str) -> Dict[str, Any]:
        """
        Load session data given a session ID.

        Args:
            session_id: str
        """
        pass

    @abstractmethod
    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        """
        Save session data.

        Args:
            session_id: str
            data: Dict
            timeout: int (in seconds)
        """
        pass

class InMemorySessionBackend(SessionBackend):
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.last_access: Dict[str, float] = {}

    async def load(self, session_id: str) -> Dict[str, Any]:
        now = time.time()
        if session_id in self.sessions and (now - self.last_access.get(session_id, now)) < SESSION_TIMEOUT:
            self.last_access[session_id] = now
            return self.sessions[session_id]
        return {}

    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        self.sessions[session_id] = data
        self.last_access[session_id] = time.time()


# -----------------------------
# Request Objects
# -----------------------------
current_request: contextvars.ContextVar[Any] = contextvars.ContextVar("current_request")

class Request:
    """Represents an HTTP request in the MicroPie framework."""
    def __init__(self, scope: Dict[str, Any]) -> None:
        """
        Initialize a new Request instance.

        Args:
            scope: The ASGI scope dictionary for the request.
        """
        self.scope: Dict[str, Any] = scope
        self.method: str = scope.get("method", "")
        self.path_params: List[str] = []
        self.query_params: Dict[str, List[str]] = {}
        self.body_params: Dict[str, List[str]] = {}
        self.get_json: Any = {}
        self.session: Dict[str, Any] = {}
        self.files: Dict[str, Any] = {}
        self.headers: Dict[str, str] = {
            k.decode("utf-8", errors="replace").lower(): v.decode("utf-8", errors="replace")
            for k, v in scope.get("headers", [])
        }

class WebSocketRequest(Request):
    """Represents a WebSocket request in the MicroPie framework."""
    def __init__(self, scope: Dict[str, Any]) -> None:
        super().__init__(scope)

class WebSocket:
    """Manages WebSocket communication in the MicroPie framework."""
    def __init__(self, receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Initialize a WebSocket instance.

        Args:
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        self.receive = receive
        self.send = send
        self.accepted = False
        self.session_id: Optional[str] = None

    async def accept(self, subprotocol: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """
        Accept the WebSocket connection.

        Args:
            subprotocol: Optional subprotocol to use.
            session_id: Optional session ID to set in a cookie during the handshake.
        """
        if self.accepted:
            raise RuntimeError("WebSocket connection already accepted")
        # Handle initial connect event
        message = await self.receive()
        if message["type"] != "websocket.connect":
            raise ValueError(f"Expected websocket.connect, got {message['type']}")
        headers = []
        if session_id:
            headers.append(("Set-Cookie", f"session_id={session_id}; Path=/; SameSite=Lax; HttpOnly; Secure;"))
            self.session_id = session_id
        await self.send({
            "type": "websocket.accept",
            "subprotocol": subprotocol,
            "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers]
        })
        self.accepted = True

    async def receive_text(self) -> str:
        """
        Receive a text message from the WebSocket.

        Returns:
            The received text message.

        Raises:
            ConnectionClosed: If the connection is closed.
            ValueError: If an unexpected message type is received.
        """
        message = await self.receive()
        if message["type"] == "websocket.receive":
            return message.get("text", message.get("bytes", b"").decode("utf-8", "ignore"))
        elif message["type"] == "websocket.disconnect":
            raise ConnectionClosed()
        raise ValueError(f"Unexpected message type: {message['type']}")

    async def receive_bytes(self) -> bytes:
        """
        Receive a binary message from the WebSocket.

        Returns:
            The received binary message.

        Raises:
            ConnectionClosed: If the connection is closed.
            ValueError: If an unexpected message type is received.
        """
        message = await self.receive()
        if message["type"] == "websocket.receive":
            return message.get("bytes", b"") or message.get("text", "").encode("utf-8")
        elif message["type"] == "websocket.disconnect":
            raise ConnectionClosed()
        raise ValueError(f"Unexpected message type: {message['type']}")

    async def send_text(self, data: str) -> None:
        """
        Send a text message over the WebSocket.

        Args:
            data: The text message to send.

        Raises:
            RuntimeError: If the connection is not accepted.
        """
        if not self.accepted:
            raise RuntimeError("WebSocket connection not accepted")
        await self.send({
            "type": "websocket.send",
            "text": data
        })

    async def send_bytes(self, data: bytes) -> None:
        """
        Send a binary message over the WebSocket.

        Args:
            data: The binary message to send.

        Raises:
            RuntimeError: If the connection is not accepted.
        """
        if not self.accepted:
            raise RuntimeError("WebSocket connection not accepted")
        await self.send({
            "type": "websocket.send",
            "bytes": data
        })

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """
        Close the WebSocket connection.

        Args:
            code: The closure code (default: 1000).
            reason: Optional reason for closure.
        """
        if self.accepted:
            await self.send({
                "type": "websocket.close",
                "code": code,
                "reason": reason or ""
            })
            self.accepted = False

class ConnectionClosed(Exception):
    """Raised when a WebSocket connection is closed."""
    pass


# -----------------------------
# Middleware Abstraction
# -----------------------------
class HttpMiddleware(ABC):
    """
    Pluggable middleware class that allows hooking into the HTTP request lifecycle.
    """
    @abstractmethod
    async def before_request(self, request: Request) -> Optional[Dict]:
        """
        Called before the HTTP request is processed.
        
        Args:
            request: The Request object.
        
        Returns:
            Optional dictionary with response details (status_code, body, headers) to short-circuit the request,
            or None to continue processing.
        """
        pass

    @abstractmethod
    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        """
        Called after the HTTP request is processed, but before the final response is sent.
        
        Args:
            request: The Request object.
            status_code: The HTTP status code.
            response_body: The response body.
            extra_headers: List of header tuples.
        
        Returns:
            Optional dictionary with updated response details (status_code, body, headers), or None to use defaults.
        """
        pass

class WebSocketMiddleware(ABC):
    """
    Pluggable middleware class that allows hooking into the WebSocket request lifecycle.
    """
    @abstractmethod
    async def before_websocket(self, request: WebSocketRequest) -> Optional[Dict]:
        """
        Called before the WebSocket handler is invoked.
        
        Args:
            request: The WebSocketRequest object.
        
        Returns:
            Optional dictionary with close details (code, reason) to reject the connection,
            or None to continue processing.
        """
        pass

    @abstractmethod
    async def after_websocket(self, request: WebSocketRequest) -> None:
        """
        Called after the WebSocket handler completes.
        
        Args:
            request: The WebSocketRequest object.
        """
        pass


# -----------------------------
# Application Base
# -----------------------------
class App:
    """
    ASGI application for handling HTTP and WebSocket requests in MicroPie.
    It supports pluggable session backends via the 'session_backend' attribute,
    pluggable HTTP middlewares via the 'middlewares' list, WebSocket middlewares via the 'ws_middlewares' list,
    and startup/shutdown handlers via 'on_startup' and 'on_shutdown' methods.
    """
    def __init__(self, session_backend: Optional[SessionBackend] = None) -> None:
        if JINJA_INSTALLED:
            self.env = Environment(
                loader=FileSystemLoader("templates"),
                autoescape=select_autoescape(["html", "xml"]),
                enable_async=True
            )
        else:
            self.env = None
        self.session_backend: SessionBackend = session_backend or InMemorySessionBackend()
        self.middlewares: List[HttpMiddleware] = []
        self.ws_middlewares: List[WebSocketMiddleware] = []
        self.startup_handlers: List[Callable[[], Awaitable[None]]] = []
        self.shutdown_handlers: List[Callable[[], Awaitable[None]]] = []
        self._started: bool = False

    @property
    def request(self) -> Request:
        """
        Retrieve the current request from the context variable.

        Returns: The current Request instance.
        """
        return current_request.get()

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        ASGI callable interface for the server.

        Args:
            scope: The ASGI scope dictionary.
            receive: The callable to receive ASGI events.
            send: The callable to send ASGI events.
        """
        if scope["type"] == "http":
            await self._asgi_app_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._asgi_app_websocket(scope, receive, send)
        elif scope["type"] == "lifespan":
            await self._asgi_app_lifespan(receive, send)
        else:
            pass  # Ignore other scopes for now

    async def _asgi_app_lifespan(
        self,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Handle ASGI lifespan events for startup and shutdown.

        Args:
            receive: The callable to receive ASGI lifespan events.
            send: The callable to send ASGI lifespan events.
        """
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    if not self._started:
                        for handler in self.startup_handlers:
                            await handler()
                        self._started = True
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
                    return
            elif message["type"] == "lifespan.shutdown":
                try:
                    if self._started:
                        for handler in self.shutdown_handlers:
                            await handler()
                        self._started = False
                    await send({"type": "lifespan.shutdown.complete"})
                except Exception as e:
                    await send({"type": "lifespan.shutdown.failed", "message": str(e)})
                return

    async def _asgi_app_http(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        ASGI application entry point for handling HTTP requests.

        Args:
            scope: The ASGI scope dictionary.
            receive: The callable to receive ASGI events.
            send: The callable to send ASGI events.
        """
        request: Request = Request(scope)
        token = current_request.set(request)
        status_code: int = 200
        response_body: Any = ""
        extra_headers: List[Tuple[str, str]] = []
        try:
            # Parse request details (query params, cookies, session)
            request.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
            cookies = self._parse_cookies(request.headers.get("cookie", ""))
            request.session = await self.session_backend.load(cookies.get("session_id", "")) or {}

            # Parse body parameters for POST, PUT, PATCH requests
            if request.method in ("POST", "PUT", "PATCH"):
                body_data = bytearray()
                while True:
                    msg: Dict[str, Any] = await receive()
                    body_data += msg.get("body", b"")
                    if not msg.get("more_body"):
                        break
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        request.get_json = json.loads(body_data.decode("utf-8"))
                        if isinstance(request.get_json, dict):
                            request.body_params = {k: [str(v)] for k, v in request.get_json.items()}
                    except:
                        await self._send_response(send, 400, "400 Bad Request: Bad JSON")
                        return
                elif "multipart/form-data" in content_type:
                    if not MULTIPART_INSTALLED:
                        print("For multipart form data support install 'multipart'.")
                        await self._send_response(send, 500, "500 Internal Server Error")
                        return
                    if boundary := re.search(r"boundary=([^;]+)", content_type):
                        reader = asyncio.StreamReader()
                        reader.feed_data(body_data)
                        reader.feed_eof()
                        request.body_params, request.files = await self._parse_multipart(reader, boundary.group(1).encode("utf-8"))
                    else:
                        await self._send_response(send, 400, "400 Bad Request: Missing boundary")
                        return
                else:
                    # Default to application/x-www-form-urlencoded
                    request.body_params = parse_qs(body_data.decode("utf-8", "ignore"))

            # Now run middleware before_request with populated request data
            for mw in self.middlewares:
                if result := await mw.before_request(request):
                    status_code, response_body, extra_headers = (
                        result["status_code"],
                        result["body"],
                        result.get("headers", []),
                    )
                    await self._send_response(send, status_code, response_body, extra_headers)
                    return

            # Parse path and find handler
            path: str = scope["path"].lstrip("/")
            parts: List[str] = path.split("/") if path else []
            # Check if request._route_handler has been set by middleware
            if hasattr(request, "_route_handler"):
                func_name: str = request._route_handler
            else:
                func_name: str = parts[0] if parts else "index"
                if func_name.startswith("_") or func_name.startswith("ws_"):
                    await self._send_response(send, 404, "404 Not Found")
                    return

            # Respect path_params set in middleware
            if not request.path_params:
                request.path_params = parts[1:] if len(parts) > 1 else []
            handler = getattr(self, func_name, None) or getattr(self, "index", None)
            if not handler:
                await self._send_response(send, 404, "404 Not Found")
                return

            # Build function arguments from path, query, body, files, and session values
            sig = inspect.signature(handler)
            func_args: List[Any] = []
            path_params_copy = request.path_params[:]  # Create a copy to avoid modifying original
            for param in sig.parameters.values():
                if param.name == "self":  # Skip self parameter
                    continue
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    # Pass all remaining path_params for *args
                    func_args.extend(path_params_copy)
                    path_params_copy = []  # Clear to prevent reuse
                    continue  # Skip appending anything else
                param_value = None
                if path_params_copy:
                    param_value = path_params_copy.pop(0)
                elif param.name in request.query_params:
                    param_value = request.query_params[param.name][0]
                elif param.name in request.body_params:
                    param_value = request.body_params[param.name][0]
                elif param.name in request.files:
                    param_value = request.files[param.name]
                elif param.name in request.session:
                    param_value = request.session[param.name]
                elif param.default is not param.empty:
                    param_value = param.default
                else:
                    status_code = 400
                    response_body = f"400 Bad Request: Missing required parameter '{param.name}'"
                    await self._send_response(send, status_code, response_body)
                    return
                func_args.append(param_value)

            if handler == getattr(self, "index", None) and not func_args and path and path != "index":
                await self._send_response(send, 404, "404 Not Found")
                return

            # Execute handler
            try:
                result = await handler(*func_args) if inspect.iscoroutinefunction(handler) else handler(*func_args)
            except Exception as e:
                print(f"Request error: {e}")
                await self._send_response(send, 500, "500 Internal Server Error")
                return

            # Normalize response
            if isinstance(result, tuple):
                status_code, response_body = result[0], result[1]
                extra_headers = result[2] if len(result) > 2 else []
            else:
                response_body = result
            if isinstance(response_body, (dict, list)):
                response_body = json.dumps(response_body)
                extra_headers.append(("Content-Type", "application/json"))

            # Save session
            if request.session:
                session_id = cookies.get("session_id") or str(uuid.uuid4())
                await self.session_backend.save(session_id, request.session, SESSION_TIMEOUT)
                if not cookies.get("session_id"):
                    extra_headers.append(("Set-Cookie", f"session_id={session_id}; Path=/; SameSite=Lax; HttpOnly; Secure;"))

            # Middleware: after request
            for mw in self.middlewares:
                if result := await mw.after_request(request, status_code, response_body, extra_headers):
                    status_code, response_body, extra_headers = (
                        result.get("status_code", status_code),
                        result.get("body", response_body),
                        result.get("headers", extra_headers)
                    )

            await self._send_response(send, status_code, response_body, extra_headers)

        finally:
            current_request.reset(token)

    async def _asgi_app_websocket(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        ASGI application entry point for handling WebSocket requests.

        Args:
            scope: The ASGI scope dictionary.
            receive: The callable to receive ASGI events.
            send: The callable to send ASGI events.
        """
        request: WebSocketRequest = WebSocketRequest(scope)
        token = current_request.set(request)
        try:
            # Parse request details (query params, cookies, session)
            request.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
            cookies = self._parse_cookies(request.headers.get("cookie", ""))
            request.session = await self.session_backend.load(cookies.get("session_id", "")) or {}

            # Run WebSocket middleware before_websocket
            for mw in self.ws_middlewares:
                if result := await mw.before_websocket(request):
                    code, reason = result.get("code", 1008), result.get("reason", "Middleware rejected")
                    await self._send_websocket_close(send, code, reason)
                    return

            # Parse path and find handler
            path: str = scope["path"].lstrip("/")
            parts: List[str] = path.split("/") if path else []
            func_name: str = parts[0] if parts else "ws_index"
            if func_name.startswith("_"):
                await self._send_websocket_close(send, 1008, "Private handler not allowed")
                return

            # Map WebSocket handler (e.g., /chat -> ws_chat)
            handler_name = f"ws_{func_name}" if func_name else "ws_index"
            if hasattr(request, "_ws_route_handler"):
                handler_name = request._ws_route_handler
            request.path_params = parts[1:] if len(parts) > 1 else []
            handler = getattr(self, handler_name, None)
            if not handler:
                await self._send_websocket_close(send, 1008, "No matching WebSocket route")
                return

            # Build function arguments
            sig = inspect.signature(handler)
            func_args: List[Any] = []
            path_params_copy = request.path_params[:]
            ws = WebSocket(receive, send)
            func_args.append(ws)  # First non-self parameter is WebSocket object
            for param in sig.parameters.values():
                if param.name in ("self", "ws"):  # Skip self and ws parameters
                    continue
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    func_args.extend(path_params_copy)
                    path_params_copy = []
                    continue
                param_value = None
                if path_params_copy:
                    param_value = path_params_copy.pop(0)
                elif param.name in request.query_params:
                    param_value = request.query_params[param.name][0]
                elif param.name in request.session:
                    param_value = request.session[param.name]
                elif param.default is not param.empty:
                    param_value = param.default
                else:
                    await self._send_websocket_close(send, 1008, f"Missing required parameter '{param.name}'")
                    return
                func_args.append(param_value)

            # Set session ID if needed
            session_id = cookies.get("session_id") or str(uuid.uuid4())
            ws.session_id = session_id

            # Execute handler
            try:
                await handler(*func_args)
            except ConnectionClosed:
                pass  # Normal closure, no need to send another close message
            except Exception as e:
                print(f"WebSocket error: {e}")
                await self._send_websocket_close(send, 1011, f"Handler error: {str(e)}")
                return

            # Save session
            if request.session:
                await self.session_backend.save(ws.session_id, request.session, SESSION_TIMEOUT)

            # Run WebSocket middleware after_websocket
            for mw in self.ws_middlewares:
                await mw.after_websocket(request)

        finally:
            current_request.reset(token)

    def _parse_cookies(self, cookie_header: str) -> Dict[str, str]:
        """
        Parse the Cookie header and return a dictionary of cookie names and values.

        Args:
            cookie_header: The raw Cookie header string.

        Returns:
            A dictionary mapping cookie names to their corresponding values.
        """
        cookies: Dict[str, str] = {}
        if not cookie_header:
            return cookies
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                k, v = cookie.strip().split("=", 1)
                cookies[k] = v
        return cookies

    async def _parse_multipart(self, reader: asyncio.StreamReader, boundary: bytes) -> Optional[Tuple[Dict[str, List[str]], Dict[str, Any]]]:
        """
        Asynchronously parses a multipart form-data request.

        This method processes incoming multipart form-data, handling
        both text fields and file uploads. File data is streamed to the handler
        via an asyncio.Queue.

        Args:
            reader (asyncio.StreamReader): The stream reader from which
                to read the multipart data.
            boundary (bytes): The boundary string used to separate form
                fields in the multipart request.

        Returns:
            tuple[dict, dict]: A tuple containing form_data and files.
        """
        with PushMultipartParser(boundary) as parser:
            form_data: dict = {}
            files: dict = {}
            current_field_name: Optional[str] = None
            current_filename: Optional[str] = None
            current_content_type: Optional[str] = None
            current_queue: Optional[asyncio.Queue] = None
            form_value: str = ""
            while not parser.closed:
                chunk: bytes = await reader.read(65536)
                if not chunk:
                    break
                for result in parser.parse(chunk):
                    if isinstance(result, MultipartSegment):
                        current_field_name = result.name
                        current_filename = result.filename
                        current_content_type = None
                        form_value = ""
                        if current_queue:
                            await current_queue.put(None)  # Signal end of previous file stream
                            current_queue = None
                        for header, value in result.headerlist:
                            if header.lower() == "content-type":
                                current_content_type = value
                        if current_filename:
                            current_queue = asyncio.Queue()
                            files[current_field_name] = {
                                "filename": current_filename,
                                "content_type": current_content_type or "application/octet-stream",
                                "content": current_queue,
                            }
                        else:
                            form_data[current_field_name] = []
                    elif result:
                        if current_queue:
                            await current_queue.put(result)
                        else:
                            form_value += result.decode("utf-8", "ignore")
                    else:
                        if current_queue:
                            await current_queue.put(None)  # Signal end of file stream
                            current_queue = None
                        else:
                            if form_value and current_field_name:
                                form_data[current_field_name].append(form_value)
                            form_value = ""
            # Ensure any remaining form_value or file stream is processed
            if current_field_name and form_value and not current_filename:
                form_data[current_field_name].append(form_value)
            if current_queue:
                await current_queue.put(None)  # Signal end of final file stream
            return form_data, files

    async def _send_response(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        status_code: int,
        body: Any,
        extra_headers: Optional[List[Tuple[str, str]]] = None
    ) -> None:
        """
        Send an HTTP response using the ASGI send callable.

        Args:
            send: The ASGI send callable.
            status_code: The HTTP status code for the response.
            body: The response body, which may be a string, bytes, or
            generator.
            extra_headers: Optional list of extra header tuples.
        """
        if extra_headers is None:
            extra_headers = []
        sanitized_headers: List[Tuple[str, str]] = []
        for k, v in extra_headers:
            if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
                print(f"Header injection attempt detected: {k}: {v}")
                continue
            sanitized_headers.append((k, v))
        if not any(h[0].lower() == "content-type" for h in sanitized_headers):
            sanitized_headers.append(("Content-Type", "text/html; charset=utf-8"))
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in sanitized_headers],
        })
        if hasattr(body, "__aiter__"):
            async for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, str)):
            for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        response_body = (body if isinstance(body, bytes)
                         else str(body).encode("utf-8"))
        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False
        })

    async def _send_websocket_response(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        status_code: int,
        body: bytes,
        extra_headers: List[Tuple[str, str]]
    ) -> None:
        """
        Send an HTTP response for WebSocket-related headers (e.g., cookies).

        Args:
            send: The ASGI send callable.
            status_code: The HTTP status code.
            body: The response body.
            extra_headers: List of header tuples.
        """
        sanitized_headers: List[Tuple[str, str]] = []
        for k, v in extra_headers:
            if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
                print(f"Header injection attempt detected: {k}: {v}")
                continue
            sanitized_headers.append((k, v))
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in sanitized_headers],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False
        })

    async def _send_websocket_close(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        code: int,
        reason: str
    ) -> None:
        """
        Send a WebSocket close message.

        Args:
            send: The ASGI send callable.
            code: The closure code.
            reason: The reason for closure.
        """
        await send({
            "type": "websocket.close",
            "code": code,
            "reason": reason
        })

    def _redirect(self, location: str, extra_headers: list = None) -> Tuple[int, str, List[Tuple[str, str]]]:
        """
        Generate an HTTP redirect response.
        Args:
            location: The URL to redirect to.
            extra_headers: Optional list of tuples (header_name, header_value) to include in the response.
        Returns:
            A tuple containing the HTTP status code, the HTML body, and headers list.
        """
        headers = [("Location", location)]
        if extra_headers:
            headers.extend(extra_headers)
        return 302, "", headers

    async def _render_template(self, name: str, **kwargs: Any) -> str:
        """
        Render a template asynchronously using Jinja2.

        Args:
            name: The name of the template file.
            **kwargs: Additional keyword arguments for the template.

        Returns:
            The rendered template as a string.
        """
        if not JINJA_INSTALLED:
            print("To use the `_render_template` method install 'jinja2'.")
            return "500 Internal Server Error: Jinja2 not installed."
        assert self.env is not None
        template = await asyncio.to_thread(self.env.get_template, name)
        return await template.render_async(**kwargs)
