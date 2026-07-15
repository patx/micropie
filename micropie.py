"""
MicroPie: An ultra micro ASGI web framework.

Homepage: https://patx.github.io/micropie

Copyright (c) 2025, Harrison Erd.
License: BSD3 (see LICENSE for details)
"""

__author__ = "Harrison Erd"
__license__ = "BSD3"

import asyncio
import contextvars
import inspect
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import parse_qs, urlsplit, urlunsplit, quote

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


logger = logging.getLogger(__name__)


_PARAM_EMPTY = inspect.Parameter.empty
_VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
_POSITIONAL_PARAM_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.VAR_POSITIONAL,
)
_DEFAULT_CONTENT_TYPE = ("Content-Type", "text/html; charset=utf-8")
_JSON_CONTENT_TYPE = ("Content-Type", "application/json")
_DEFAULT_HEADER_BYTES = (b"Content-Type", b"text/html; charset=utf-8")
_JSON_HEADER_BYTES = (b"Content-Type", b"application/json")
_DEFAULT_HEADERS_BYTES = [_DEFAULT_HEADER_BYTES]
_JSON_HEADERS_BYTES = [_JSON_HEADER_BYTES]
_ROUTE_ATTR_MISSING = object()
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _format_session_cookie(session_id: str, *, secure: bool) -> str:
    attributes = [
        f"session_id={session_id}",
        "Path=/",
        "SameSite=Lax",
        "HttpOnly",
    ]
    if secure:
        attributes.append("Secure")
    return "; ".join(attributes) + ";"


def _parse_urlencoded(data: bytes) -> Dict[str, List[str]]:
    """Parse URL-encoded data without dropping blanks or malformed fields."""
    try:
        encoded = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("URL-encoded input must be ASCII") from exc
    if _INVALID_PERCENT_ESCAPE.search(encoded):
        raise ValueError("Invalid percent escape in URL-encoded input")
    try:
        return parse_qs(
            encoded,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Malformed URL-encoded input") from exc


class _HandlerParam(NamedTuple):
    name: str
    kind: Any
    default: Any


class _HandlerInfo(NamedTuple):
    params: Tuple[_HandlerParam, ...]
    accepts_params: bool
    is_coroutine: bool


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
        self.timeouts: Dict[str, int] = {}
        self._next_cleanup: float = 0.0
        self._cleanup_interval: float = 60.0

    def _cleanup(self, now: Optional[float] = None, *, force: bool = False):
        """Remove sessions whose configured inactivity timeout has elapsed."""
        if now is None:
            now = time.time()
        if not force and now < self._next_cleanup:
            return
        self._next_cleanup = now + self._cleanup_interval
        expired = [
            sid
            for sid, ts in self.last_access.items()
            if now - ts >= self.timeouts.get(sid, SESSION_TIMEOUT)
        ]
        for sid in expired:
            self.sessions.pop(sid, None)
            self.last_access.pop(sid, None)
            self.timeouts.pop(sid, None)

    async def load(self, session_id: str) -> Dict[str, Any]:
        now = time.time()
        self._cleanup(now)
        last_access = self.last_access.get(session_id)
        if last_access is not None:
            timeout = self.timeouts.get(session_id, SESSION_TIMEOUT)
            if now - last_access >= timeout:
                self.sessions.pop(session_id, None)
                self.last_access.pop(session_id, None)
                self.timeouts.pop(session_id, None)
                return {}
            self.last_access[session_id] = now
            return self.sessions.get(session_id, {})
        return {}

    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        self._cleanup()
        if not data or timeout <= 0:
            # treat empty as delete
            self.sessions.pop(session_id, None)
            self.last_access.pop(session_id, None)
            self.timeouts.pop(session_id, None)
        else:
            self.sessions[session_id] = data
            self.last_access[session_id] = time.time()
            self.timeouts[session_id] = timeout


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
        self.body_params: Dict[str, List[str]] = scope.get("body_params", {})
        self._json: Any = scope.get("json_body", {})
        self.session: Dict[str, Any] = scope.get("session", {})
        self.files: Dict[str, Any] = scope.get("files", {})
        self.headers: Dict[str, str] = {
            k.decode("utf-8", errors="replace").lower(): v.decode(
                "utf-8", errors="replace"
            )
            for k, v in scope.get("headers", [])
        }
        self.body_parsed: bool = scope.get("body_parsed", False)

    def query(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Return the first value for a query parameter.

        Args:
            name: Query parameter name.
            default: Value returned when the parameter is missing.
        """
        values = self.query_params.get(name)
        if values:
            return values[0]
        return default

    def form(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Return the first value for a form/body parameter.

        Args:
            name: Form field name.
            default: Value returned when the parameter is missing.
        """
        values = self.body_params.get(name)
        if values:
            return values[0]
        return default

    def json(self, name: Optional[str] = None, default: Any = None) -> Any:
        """
        Return the parsed JSON body or a value from a top-level JSON object.

        Args:
            name: Optional key from the top-level JSON object.
            default: Value returned when key is missing or payload is not an object.
        """
        if name is None:
            return self._json
        if isinstance(self._json, dict):
            return self._json.get(name, default)
        return default


class WebSocketRequest(Request):
    """Represents a WebSocket request in the MicroPie framework."""

    def __init__(self, scope: Dict[str, Any]) -> None:
        super().__init__(scope)


class WebSocket:
    """Manages WebSocket communication in the MicroPie framework."""

    def __init__(
        self,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        *,
        session_cookie_secure: bool = True,
    ) -> None:
        """
        Initialize a WebSocket instance.

        Args:
            receive: The ASGI receive callable.
            send: The ASGI send callable.
            session_cookie_secure: Whether session cookies include the Secure flag.
        """
        self.receive = receive
        self.send = send
        self.accepted = False
        self.session_id: Optional[str] = None
        self.session_cookie_secure = session_cookie_secure

    async def accept(
        self, subprotocol: Optional[str] = None, session_id: Optional[str] = None
    ) -> None:
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
            headers.append(
                (
                    "Set-Cookie",
                    _format_session_cookie(
                        session_id, secure=self.session_cookie_secure
                    ),
                )
            )
            self.session_id = session_id
        await self.send(
            {
                "type": "websocket.accept",
                "subprotocol": subprotocol,
                "headers": [
                    (k.encode("latin-1"), v.encode("latin-1")) for k, v in headers
                ],
            }
        )
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
            return message.get(
                "text", message.get("bytes", b"").decode("utf-8", "ignore")
            )
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
        await self.send({"type": "websocket.send", "text": data})

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
        await self.send({"type": "websocket.send", "bytes": data})

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """
        Close the WebSocket connection.

        Args:
            code: The closure code (default: 1000).
            reason: Optional reason for closure.
        """
        if self.accepted:
            await self.send(
                {"type": "websocket.close", "code": code, "reason": reason or ""}
            )
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
        extra_headers: List[Tuple[str, str]],
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
    and startup/shutdown handlers via 'startup_handlers' and 'shutdown_handlers'.
    """

    def __init__(
        self,
        session_backend: Optional[SessionBackend] = None,
        *,
        body_timeout: Optional[float] = 5.0,
        session_timeout: int = SESSION_TIMEOUT,
        session_cookie_secure: bool = True,
    ) -> None:
        if body_timeout is not None and body_timeout <= 0:
            raise ValueError("body_timeout must be positive or None")
        if session_timeout <= 0:
            raise ValueError("session_timeout must be positive")
        if JINJA_INSTALLED:
            self.env = Environment(
                loader=FileSystemLoader("templates"),
                autoescape=select_autoescape(["html", "xml"]),
                enable_async=True,
            )
        else:
            self.env = None
        self.session_backend: SessionBackend = (
            session_backend or InMemorySessionBackend()
        )
        self.body_timeout = body_timeout
        self.session_timeout = session_timeout
        self.session_cookie_secure = session_cookie_secure
        self.middlewares: List[HttpMiddleware] = []
        self.ws_middlewares: List[WebSocketMiddleware] = []
        self.startup_handlers: List[Callable[[], Awaitable[None]]] = []
        self.shutdown_handlers: List[Callable[[], Awaitable[None]]] = []
        self._handler_cache: Dict[Any, _HandlerInfo] = {}
        self._started: bool = False

    @property
    def request(self) -> Request:
        """
        Retrieve the current request from the context variable.

        Returns: The current Request instance.
        """
        return current_request.get()

    def _get_handler_info(self, handler: Callable[..., Any]) -> _HandlerInfo:
        """
        Return cached metadata needed to bind and call a route handler.
        """
        cache_key = getattr(handler, "__func__", handler)
        handler_info = self._handler_cache.get(cache_key)
        if handler_info is not None:
            return handler_info

        params = []
        accepts_params = False
        for param in inspect.signature(handler).parameters.values():
            if param.name == "self":
                continue
            if param.kind in _POSITIONAL_PARAM_KINDS:
                accepts_params = True
            params.append(_HandlerParam(param.name, param.kind, param.default))

        handler_info = _HandlerInfo(
            tuple(params), accepts_params, inspect.iscoroutinefunction(handler)
        )
        self._handler_cache[cache_key] = handler_info
        return handler_info

    def _resolve_route_handler(
        self, handler_name: str
    ) -> Tuple[Optional[Callable[..., Any]], bool]:
        """
        Return a callable route handler and whether the route attribute exists.
        """
        raw_handler = inspect.getattr_static(
            self, handler_name, _ROUTE_ATTR_MISSING
        )
        if raw_handler is _ROUTE_ATTR_MISSING:
            return None, False
        if isinstance(raw_handler, property):
            return None, True
        if not callable(raw_handler):
            if inspect.isdatadescriptor(raw_handler) or not hasattr(
                raw_handler, "__get__"
            ):
                return None, True

        try:
            handler = getattr(self, handler_name, _ROUTE_ATTR_MISSING)
        except Exception:
            return None, True
        if handler is _ROUTE_ATTR_MISSING:
            return None, False
        if not callable(handler):
            return None, True
        return handler, True

    async def _load_session_from_scope(
        self, scope: Dict[str, Any], cookies: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Return an existing ASGI session or load one when a session cookie exists.
        """
        if "session" in scope:
            return scope["session"]
        session_id = cookies.get("session_id")
        if not session_id:
            return {}
        return await self.session_backend.load(session_id) or {}

    def _parse_query_string(self, scope: Dict[str, Any]) -> Dict[str, List[str]]:
        query_string = scope.get("query_string", b"")
        if not query_string:
            return {}
        return _parse_urlencoded(query_string)

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
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
        send: Callable[[Dict[str, Any]], Awaitable[None]],
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
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        ASGI application entry point for handling HTTP requests.
        """
        request: Request = Request(scope)
        token = current_request.set(request)
        status_code: int = 200
        response_body: Any = ""
        extra_headers: List[Tuple[str, str]] = []
        parse_task: Optional[asyncio.Task] = (
            None  # background multipart task if started
        )
        multipart_file_notifications: Optional[asyncio.Queue] = None

        async def _cancel_parse_task():
            if parse_task is None:
                return
            if not parse_task.done():
                parse_task.cancel()
            try:
                await parse_task
            except asyncio.CancelledError:
                pass
            except Exception:
                # The parser runner logs the original exception.
                pass

        async def _early_exit(
            code: int, body: Any, headers: Optional[List[Tuple[str, str]]] = None
        ):
            await _cancel_parse_task()
            await self._send_response(send, code, body, headers or [])
            return

        async def _await_file_param(name: str) -> Optional[Any]:
            """
            Wait until a multipart file field named `name` is available in request.files,
            or until the background parse_task (if any) completes.
            """
            if name in request.files:
                return request.files[name]
            if parse_task is None or multipart_file_notifications is None:
                return None
            while name not in request.files:
                if parse_task.done():
                    try:
                        await parse_task
                    except Exception:
                        # The parser runner logs the original exception.
                        pass
                    break
                await multipart_file_notifications.get()
            return request.files.get(name)

        try:
            # Parse query/cookies/session
            try:
                request.query_params = self._parse_query_string(scope)
            except ValueError:
                await _early_exit(400, "400 Bad Request: Malformed query string")
                return
            cookie_header = request.headers.get("cookie", "")
            cookies = self._parse_cookies(cookie_header) if cookie_header else {}
            request.session = await self._load_session_from_scope(scope, cookies)
            content_type = request.headers.get("content-type", "")

            # Body parsing setup
            if (
                request.method in ("POST", "PUT", "PATCH")
                and not request.body_parsed
                and not request.body_params
            ):
                if "multipart/form-data" in content_type:
                    if not MULTIPART_INSTALLED:
                        logger.error(
                            "Multipart form data requires the 'multipart' package"
                        )
                        await _early_exit(500, "500 Internal Server Error")
                        return
                    boundary_match = re.search(r"boundary=([^;]+)", content_type)
                    if not boundary_match:
                        await _early_exit(400, "400 Bad Request: Missing boundary")
                        return
                    multipart_file_notifications = asyncio.Queue()

                    async def _run_multipart_parser() -> None:
                        try:
                            await self._parse_multipart_into_request(
                                receive,
                                boundary_match.group(1).encode("utf-8"),
                                request,
                                file_notifications=multipart_file_notifications,
                                file_queue_maxsize=2048,
                            )
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            logger.exception("Failed to parse multipart request body")
                            raise
                        finally:
                            multipart_file_notifications.put_nowait(None)

                    # Parse in the background so handlers can drain file queues
                    # while later upload chunks are still arriving.
                    parse_task = asyncio.create_task(_run_multipart_parser())
                else:
                    body_chunks: List[bytes] = []
                    try:
                        while True:
                            if self.body_timeout is None:
                                msg = await receive()
                            else:
                                async with asyncio.timeout(self.body_timeout):
                                    msg = await receive()
                            if chunk := msg.get("body", b""):
                                body_chunks.append(chunk)
                            if not msg.get("more_body"):
                                break
                    except asyncio.TimeoutError:
                        await _early_exit(
                            408, "408 Request Timeout: Failed to receive body"
                        )
                        return
                    if len(body_chunks) == 1:
                        body_data = body_chunks[0]
                    else:
                        body_data = b"".join(body_chunks)
                    if "application/json" in content_type:
                        try:
                            request._json = json.loads(body_data)
                        except Exception:
                            await _early_exit(400, "400 Bad Request: Bad JSON")
                            return
                    else:
                        try:
                            request.body_params = _parse_urlencoded(body_data)
                        except ValueError:
                            await _early_exit(
                                400, "400 Bad Request: Malformed form body"
                            )
                            return
                    request.body_parsed = True

            # HTTP middlewares (before)
            for mw in self.middlewares:
                if result := await mw.before_request(request):
                    status_code, response_body, extra_headers = (
                        result["status_code"],
                        result["body"],
                        result.get("headers", []),
                    )
                    await _early_exit(status_code, response_body, extra_headers)
                    return

            # Subapp handoff
            if hasattr(request, "_subapp"):
                # If we started a multipart parse, cancel it before handing off
                await _cancel_parse_task()
                new_scope = dict(scope)
                new_scope["path"] = request._subapp_path
                mount = getattr(request, "_subapp_mount_path", "").strip("/")
                if mount:
                    new_scope["root_path"] = scope.get("root_path", "") + "/" + mount
                else:
                    new_scope["root_path"] = scope.get("root_path", "")
                new_scope["body_params"] = request.body_params
                new_scope["body_parsed"] = request.body_parsed
                new_scope["json_body"] = request._json
                new_scope["files"] = request.files
                new_scope["session"] = request.session

                async def subapp_receive():
                    if request.body_parsed or request.body_params:
                        return {"type": "http.request", "body": b"", "more_body": False}
                    return await receive()

                await request._subapp(new_scope, subapp_receive, send)
                return

            # Routing
            path: str = scope["path"].lstrip("/")
            parts: List[str] = path.split("/") if path else []
            if hasattr(request, "_route_handler"):
                func_name: str = request._route_handler
            else:
                func_name: str = parts[0] if parts else "index"
                if func_name.startswith("_") or func_name.startswith("ws_"):
                    await _early_exit(404, "404 Not Found")
                    return

            if not request.path_params:
                request.path_params = parts[1:] if len(parts) > 1 else []
            handler, route_exists = self._resolve_route_handler(func_name)
            index_handler, _ = self._resolve_route_handler("index")
            if handler is None:
                if route_exists:
                    await _early_exit(404, "404 Not Found")
                    return
                handler = index_handler
            if handler is None:
                await _early_exit(404, "404 Not Found")
                return
            handler_info = self._get_handler_info(handler)

            # Initialize func_args early to avoid UnboundLocalError
            func_args: List[Any] = []

            # Check if index handler accepts parameters (for non-root paths)
            if handler == index_handler and path and path != "index":
                if not handler_info.accepts_params:
                    await _early_exit(404, "404 Not Found")
                    return
                request.path_params = parts  # Pass all path parts to index handler

            # Build handler args from untrusted request inputs only. Session
            # state stays in request.session and is never part of this namespace.
            path_params = request.path_params
            path_param_index = 0
            path_param_count = len(path_params)
            is_multipart = "multipart/form-data" in content_type
            query_params = request.query_params
            body_params = request.body_params
            json_params = request._json if isinstance(request._json, dict) else {}
            files = request.files

            for param in handler_info.params:
                if param.kind == _VAR_POSITIONAL:
                    func_args.extend(path_params[path_param_index:])
                    path_param_index = path_param_count
                    continue

                param_value = None

                if path_param_index < path_param_count:
                    param_value = path_params[path_param_index]
                    path_param_index += 1
                elif param.name in query_params:
                    param_value = query_params[param.name][0]
                elif param.name in body_params:
                    param_value = body_params[param.name][0]
                elif param.name in json_params:
                    param_value = json_params[param.name]
                elif param.name in files:
                    param_value = files[param.name]
                elif is_multipart:
                    param_value = await _await_file_param(param.name)
                    if param_value is None and param.default is _PARAM_EMPTY:
                        await _early_exit(
                            400,
                            f"400 Bad Request: Missing required parameter '{param.name}'",
                        )
                        return
                    if param_value is None:
                        param_value = param.default
                elif param.default is not _PARAM_EMPTY:
                    param_value = param.default
                else:
                    await _early_exit(
                        400,
                        f"400 Bad Request: Missing required parameter '{param.name}'",
                    )
                    return

                func_args.append(param_value)

            # Execute handler
            try:
                result = (
                    await handler(*func_args)
                    if handler_info.is_coroutine
                    else handler(*func_args)
                )
            except Exception:
                logger.exception(
                    "Unhandled exception in HTTP handler for %s", scope.get("path", "")
                )
                await _early_exit(500, "500 Internal Server Error")
                return

            # Ensure background parser (if any) is finished before finalizing response
            if parse_task is not None:
                try:
                    await parse_task
                    request.body_parsed = True
                except Exception:
                    # The parser runner logs the original exception.
                    pass

            # Normalize response
            if isinstance(result, tuple):
                status_code, response_body = result[0], result[1]
                extra_headers = result[2] if len(result) > 2 else []
            else:
                response_body = result
            if isinstance(response_body, (dict, list)):
                response_body = json.dumps(response_body)
                extra_headers.append(("Content-Type", "application/json"))

            # HTTP middlewares
            for mw in self.middlewares:
                if result := await mw.after_request(
                    request, status_code, response_body, extra_headers
                ):
                    status_code, response_body, extra_headers = (
                        result.get("status_code", status_code),
                        result.get("body", response_body),
                        result.get("headers", extra_headers),
                    )

            # Session persistence after middlewares so they can mutate request.session
            session_id = cookies.get("session_id")

            if request.session:
                # New or updated session
                if not session_id:
                    session_id = str(uuid.uuid4())
                    extra_headers.append(
                        (
                            "Set-Cookie",
                            _format_session_cookie(
                                session_id, secure=self.session_cookie_secure
                            ),
                        )
                    )
                await self.session_backend.save(
                    session_id, request.session, self.session_timeout
                )
            elif session_id:
                # Empty session and existing cookie -> treat as logout/delete
                await self.session_backend.save(session_id, {}, 0)

            # Handle async generators (e.g., SSE)
            if hasattr(response_body, "__aiter__"):
                await send(
                    {
                        "type": "http.response.start",
                        "status": status_code,
                        "headers": self._prepare_response_headers(extra_headers),
                    }
                )

                gen = response_body

                async def streamer():
                    try:
                        async for chunk in gen:
                            if isinstance(chunk, str):
                                chunk = chunk.encode("utf-8")
                            await send(
                                {
                                    "type": "http.response.body",
                                    "body": chunk,
                                    "more_body": True,
                                }
                            )
                        await send(
                            {
                                "type": "http.response.body",
                                "body": b"",
                                "more_body": False,
                            }
                        )
                    except asyncio.CancelledError:
                        raise
                    finally:
                        if hasattr(gen, "aclose"):
                            await gen.aclose()

                streaming_task = asyncio.create_task(streamer())
                try:
                    while True:
                        msg_task = asyncio.create_task(receive())
                        done, _ = await asyncio.wait(
                            [streaming_task, msg_task],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if streaming_task in done:
                            break
                        if msg_task in done:
                            msg = msg_task.result()
                            if msg["type"] == "http.disconnect":
                                streaming_task.cancel()
                                try:
                                    await streaming_task
                                except asyncio.CancelledError:
                                    pass
                                break
                finally:
                    if not streaming_task.done():
                        streaming_task.cancel()
                        try:
                            await streaming_task
                        except asyncio.CancelledError:
                            pass
                return
            else:
                await self._send_response(
                    send, status_code, response_body, extra_headers
                )

        finally:
            current_request.reset(token)

    async def _asgi_app_websocket(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
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
            try:
                request.query_params = self._parse_query_string(scope)
            except ValueError:
                await self._send_websocket_close(
                    send, 1008, "Malformed query string"
                )
                return
            cookie_header = request.headers.get("cookie", "")
            cookies = self._parse_cookies(cookie_header) if cookie_header else {}
            request.session = await self._load_session_from_scope(scope, cookies)

            # Run WebSocket middleware before_websocket
            for mw in self.ws_middlewares:
                if result := await mw.before_websocket(request):
                    code, reason = (
                        result.get("code", 1008),
                        result.get("reason", "Middleware rejected"),
                    )
                    await self._send_websocket_close(send, code, reason)
                    return

            # Parse path and find handler
            path: str = scope["path"].lstrip("/")
            parts: List[str] = path.split("/") if path else []
            func_name: str = parts[0] if parts else "ws_index"
            if func_name.startswith("_"):
                await self._send_websocket_close(
                    send, 1008, "Private handler not allowed"
                )
                return

            # Map WebSocket handler (e.g., /chat -> ws_chat)
            handler_name = f"ws_{func_name}" if func_name else "ws_index"
            if hasattr(request, "_ws_route_handler"):
                handler_name = request._ws_route_handler
            request.path_params = parts[1:] if len(parts) > 1 else []
            handler, _ = self._resolve_route_handler(handler_name)
            if handler is None:
                await self._send_websocket_close(
                    send, 1008, "No matching WebSocket route"
                )
                return
            handler_info = self._get_handler_info(handler)

            # Build function arguments
            func_args: List[Any] = []
            path_params = request.path_params
            path_param_index = 0
            path_param_count = len(path_params)
            query_params = request.query_params
            ws = WebSocket(
                receive,
                send,
                session_cookie_secure=self.session_cookie_secure,
            )
            func_args.append(ws)  # First non-self parameter is WebSocket object
            for param in handler_info.params:
                if param.name == "ws":  # Skip the WebSocket parameter
                    continue
                if param.kind == _VAR_POSITIONAL:
                    func_args.extend(path_params[path_param_index:])
                    path_param_index = path_param_count
                    continue
                param_value = None
                if path_param_index < path_param_count:
                    param_value = path_params[path_param_index]
                    path_param_index += 1
                elif param.name in query_params:
                    param_value = query_params[param.name][0]
                elif param.default is not _PARAM_EMPTY:
                    param_value = param.default
                else:
                    await self._send_websocket_close(
                        send, 1008, f"Missing required parameter '{param.name}'"
                    )
                    return
                func_args.append(param_value)

            # Set session ID if needed
            session_id = cookies.get("session_id")
            had_session_id = bool(session_id)
            ws.session_id = session_id or str(uuid.uuid4())

            # Execute handler
            try:
                await handler(*func_args)
            except ConnectionClosed:
                pass  # Normal closure, no need to send another close message
            except Exception as e:
                logger.exception(
                    "Unhandled exception in WebSocket handler for %s",
                    scope.get("path", ""),
                )
                await self._send_websocket_close(send, 1011, f"Handler error: {str(e)}")
                return

            # Run WebSocket middleware after_websocket
            for mw in self.ws_middlewares:
                await mw.after_websocket(request)

            # Save / clear session after middlewares
            if request.session:
                await self.session_backend.save(
                    ws.session_id, request.session, self.session_timeout
                )
            elif had_session_id:
                # Treat empty session as logout/delete
                await self.session_backend.save(ws.session_id, {}, 0)

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

    async def _parse_multipart_into_request(
        self,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        boundary: bytes,
        request: "Request",
        *,
        file_notifications: Optional[asyncio.Queue] = None,
        file_queue_maxsize: int = 2048,
    ) -> None:
        """
        Parse multipart directly from ASGI receive() and populate
        request.body_params / request.files as parts arrive.
        Uses bounded queues for file parts to apply backpressure.
        """
        if request.body_params is None:
            request.body_params = {}
        if request.files is None:
            request.files = {}

        with PushMultipartParser(boundary) as parser:
            current_field_name: Optional[str] = None
            current_filename: Optional[str] = None
            current_content_type: Optional[str] = None
            current_queue: Optional[asyncio.Queue] = None
            form_value: str = ""

            while True:
                msg = await receive()
                body_chunk = msg.get("body", b"")
                if body_chunk:
                    for result in parser.parse(body_chunk):
                        if isinstance(result, MultipartSegment):
                            # New part
                            current_field_name = result.name
                            current_filename = result.filename
                            current_content_type = None
                            form_value = ""

                            # Close previous file stream if open
                            if current_queue:
                                await current_queue.put(None)
                                current_queue = None

                            # Pick up content-type for this part if present
                            for header, value in result.headerlist:
                                if header.lower() == "content-type":
                                    current_content_type = value

                            if current_filename:
                                # File field → bounded queue enforces backpressure
                                current_queue = asyncio.Queue(
                                    maxsize=file_queue_maxsize
                                )
                                request.files[current_field_name] = {
                                    "filename": current_filename,
                                    "content_type": current_content_type
                                    or "application/octet-stream",
                                    "content": current_queue,
                                }
                                if file_notifications is not None:
                                    file_notifications.put_nowait(current_field_name)
                            else:
                                # Text field
                                request.body_params.setdefault(current_field_name, [])
                        elif result:
                            # Part body
                            if current_queue:
                                # May block here if handler isn't draining the queue
                                await current_queue.put(result)
                            else:
                                form_value += result.decode("utf-8", "ignore")
                        else:
                            # End of current part
                            if current_queue:
                                await current_queue.put(None)
                                current_queue = None
                            else:
                                if form_value and current_field_name:
                                    request.body_params[current_field_name].append(
                                        form_value
                                    )
                                form_value = ""

                if not msg.get("more_body"):
                    break

            # Flush leftovers
            if current_field_name and form_value and not current_filename:
                request.body_params[current_field_name].append(form_value)
            if current_queue:
                await current_queue.put(None)

    def _prepare_response_headers(
        self, extra_headers: Optional[List[Tuple[str, str]]] = None
    ) -> List[Tuple[bytes, bytes]]:
        if not extra_headers:
            return _DEFAULT_HEADERS_BYTES
        if len(extra_headers) == 1:
            if extra_headers[0] == _DEFAULT_CONTENT_TYPE:
                return _DEFAULT_HEADERS_BYTES
            if extra_headers[0] == _JSON_CONTENT_TYPE:
                return _JSON_HEADERS_BYTES

        sanitized_headers: List[Tuple[bytes, bytes]] = []
        has_content_type = False
        for k, v in extra_headers:
            if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
                logger.warning(
                    "Rejected response header containing a newline: %r: %r", k, v
                )
                continue
            if k.lower() == "content-type":
                has_content_type = True
            sanitized_headers.append((k.encode("latin-1"), v.encode("latin-1")))
        if not has_content_type:
            sanitized_headers.append(_DEFAULT_HEADER_BYTES)
        return sanitized_headers

    async def _send_response(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        status_code: int,
        body: Any,
        extra_headers: Optional[List[Tuple[str, str]]] = None,
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
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": self._prepare_response_headers(extra_headers),
            }
        )
        # Handle async generators (non-SSE cases; SSE is handled in _asgi_app_http)
        if hasattr(body, "__aiter__"):
            async for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, str)):
            for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        response_body = body if isinstance(body, bytes) else str(body).encode("utf-8")
        await send(
            {"type": "http.response.body", "body": response_body, "more_body": False}
        )

    async def _send_websocket_close(
        self, send: Callable[[Dict[str, Any]], Awaitable[None]], code: int, reason: str
    ) -> None:
        """
        Send a WebSocket close message.

        Args:
            send: The ASGI send callable.
            code: The closure code.
            reason: The reason for closure.
        """
        await send({"type": "websocket.close", "code": code, "reason": reason})

    def _encode_redirect_url(self, url: str) -> str:
        """
        Make a URL safe to put in an HTTP Location header.

        Key rule: Location must be ASCII/latin-1 -> percent-encode non-ASCII.
        We percent-encode the PATH but we do NOT touch the query string.
        """
        p = urlsplit(url)
        safe_path = quote(p.path, safe="/%")
        return urlunsplit((p.scheme, p.netloc, safe_path, p.query, p.fragment))

    def _redirect(
        self,
        location: str,
        extra_headers: list | None = None,
    ) -> Tuple[int, str, List[Tuple[str, str]]]:
        """
        Generate an HTTP redirect response.
        """
        safe_location = self._encode_redirect_url(location)

        headers = [("Location", safe_location)]
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
            logger.error("Template rendering requires the 'jinja2' package")
            return "500 Internal Server Error: Jinja2 not installed."
        assert self.env is not None
        template = await asyncio.to_thread(self.env.get_template, name)
        return await template.render_async(**kwargs)
