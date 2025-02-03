__version__ = "0.9.2"

"""
MicroPie: A simple Python ultra-micro web framework with ASGI
support. https://patx.github.io/micropie

Copyright Harrison Erd

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from this
   software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import asyncio
import contextvars
import inspect
import mimetypes
import os
import re
import time
import uuid
from typing import Any, Awaitable, BinaryIO, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA_INSTALLED = True
except ImportError:
    JINJA_INSTALLED = False

try:
    from multipart import PushMultipartParser, MultipartSegment
    MULTIPART_INSTALLED = True
except ImportError:
    MULTIPART_INSTALLED = False

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
        self.method: str = scope["method"]
        self.path_params: List[str] = []
        self.query_params: Dict[str, List[str]] = {}
        self.body_params: Dict[str, List[str]] = {}
        self.session: Dict[str, Any] = {}
        self.files: Dict[str, Any] = {}


class Server:
    """ASGI server for handling HTTP requests and WebSocket connections in MicroPie."""
    SESSION_TIMEOUT: int = 8 * 3600

    def __init__(self) -> None:
        """
        Initialize a new Server instance.

        If Jinja2 is installed, set up the template environment.
        """
        if JINJA_INSTALLED:
            self.env: Optional[Environment] = Environment(loader=FileSystemLoader("templates"))
        else:
            self.env = None
        self.sessions: Dict[str, Any] = {}

    @property
    def request(self) -> Request:
        """
        Retrieve the current request from the context variable.

        Returns:
            The current Request instance.
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
        await self._asgi_app(scope, receive, send)

    async def _asgi_app(
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
        if scope["type"] == "http":
            request: Request = Request(scope)
            token = current_request.set(request)
            try:
                method: str = scope["method"]
                path: str = scope["path"].lstrip("/")
                path_parts: List[str] = path.split("/") if path else []
                func_name: str = path_parts[0] if path_parts else "index"

                if func_name.startswith("_"):
                    await self._send_response(send, status_code=404, body="404 Not Found")
                    return

                request.path_params = path_parts[1:] if len(path_parts) > 1 else []
                handler_function: Optional[Callable[..., Any]] = getattr(self, func_name, None)
                if not handler_function:
                    request.path_params = path_parts
                    handler_function = getattr(self, "index", None)
                raw_query: bytes = scope.get("query_string", b"")
                request.query_params = parse_qs(raw_query.decode("utf-8", "ignore"))
                headers_dict: Dict[str, str] = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in scope.get("headers", [])
                }
                cookies: Dict[str, str] = self._parse_cookies(headers_dict.get("cookie", ""))
                session_id: Optional[str] = cookies.get("session_id")
                if session_id and session_id in self.sessions:
                    request.session = self.sessions[session_id]
                    request.session["last_access"] = time.time()
                else:
                    request.session = {}
                request.body_params = {}
                request.files = {}
                if method in ("POST", "PUT", "PATCH"):
                    body_data: bytearray = bytearray()
                    while True:
                        msg: Dict[str, Any] = await receive()
                        if msg["type"] == "http.request":
                            body_data += msg.get("body", b"")
                            if not msg.get("more_body"):
                                break
                    content_type: str = headers_dict.get("content-type", "")
                    if "multipart/form-data" in content_type:
                        match = re.search(r"boundary=([^;]+)", content_type)
                        if not match:
                            await self._send_response(
                                send,
                                status_code=400,
                                body="400 Bad Request: Boundary not found in Content-Type header"
                            )
                            return
                        boundary: bytes = match.group(1).encode("utf-8")
                        reader: asyncio.StreamReader = asyncio.StreamReader()
                        reader.feed_data(body_data)
                        reader.feed_eof()
                        await self._parse_multipart(reader, boundary)
                    else:
                        body_str: str = body_data.decode("utf-8", "ignore")
                        request.body_params = parse_qs(body_str)
                sig = inspect.signature(handler_function)
                func_args: List[Any] = []
                for param in sig.parameters.values():
                    if request.path_params:
                        func_args.append(request.path_params.pop(0))
                    elif param.name in request.query_params:
                        func_args.append(request.query_params[param.name][0])
                    elif param.name in request.body_params:
                        func_args.append(request.body_params[param.name][0])
                    elif param.name in request.files:
                        func_args.append(request.files[param.name])
                    elif param.name in request.session:
                        func_args.append(request.session[param.name])
                    elif param.default is not param.empty:
                        func_args.append(param.default)
                    else:
                        await self._send_response(
                            send,
                            status_code=400,
                            body=f"400 Bad Request: Missing required parameter '{param.name}'"
                        )
                        return
                if handler_function == getattr(self, "index", None) and not func_args and path:
                    await self._send_response(send, status_code=404, body="404 Not Found")
                    return
                try:
                    if inspect.iscoroutinefunction(handler_function):
                        result: Any = await handler_function(*func_args)
                    else:
                        result = handler_function(*func_args)
                except Exception as e:
                    print(f"Error processing request: {e}")
                    await self._send_response(send, status_code=500, body="500 Internal Server Error")
                    return
                status_code: int = 200
                response_body: Any = result
                extra_headers: List[Tuple[str, str]] = []
                if isinstance(result, tuple):
                    if len(result) == 2:
                        status_code, response_body = result
                    elif len(result) == 3:
                        status_code, response_body, extra_headers = result
                    else:
                        await self._send_response(
                            send,
                            status_code=500,
                            body="500 Internal Server Error: Invalid response tuple"
                        )
                        return
                if request.session:
                    session_id = cookies.get("session_id", str(uuid.uuid4()))
                    self.sessions[session_id] = request.session
                    extra_headers.append(
                        (
                            "Set-Cookie",
                            f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict"
                        )
                    )
                await self._send_response(
                    send,
                    status_code=status_code,
                    body=response_body,
                    extra_headers=extra_headers
                )
            finally:
                current_request.reset(token)
        else:
            pass

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

    async def _parse_multipart(self, reader: asyncio.StreamReader, boundary: bytes) -> None:
        """
        Parse multipart/form-data from the given reader using the specified boundary.

        Args:
            reader: An asyncio.StreamReader containing the multipart data.
            boundary: The boundary bytes extracted from the Content-Type header.
        """
        if not MULTIPART_INSTALLED:
            raise ImportError("Multipart form data not supported. Install `multipart` via pip.")
        with PushMultipartParser(boundary) as parser:
            current_field_name: Optional[str] = None
            current_filename: Optional[str] = None
            current_content_type: Optional[str] = None
            current_file: Optional[BinaryIO] = None
            form_value: str = ""
            upload_directory: str = "uploads"
            os.makedirs(upload_directory, exist_ok=True)
            while not parser.closed:
                chunk: bytes = await reader.read(65536)
                for result in parser.parse(chunk):
                    if isinstance(result, MultipartSegment):
                        current_field_name = result.name
                        current_filename = result.filename
                        current_content_type = None
                        form_value = ""
                        for header, value in result.headerlist:
                            if header.lower() == "content-type":
                                current_content_type = value
                        if current_filename:
                            safe_filename: str = f"{uuid.uuid4()}_{current_filename}"
                            file_path: str = os.path.join(upload_directory, safe_filename)
                            current_file = open(file_path, "wb")
                        else:
                            if current_field_name not in self.request.body_params:
                                self.request.body_params[current_field_name] = []
                    elif result:
                        if current_file:
                            current_file.write(result)
                        else:
                            form_value += result.decode("utf-8", "ignore")
                    else:
                        if current_file:
                            current_file.close()
                            current_file = None
                            if current_field_name:
                                self.request.files[current_field_name] = {
                                    "filename": current_filename,
                                    "content_type": current_content_type or "application/octet-stream",
                                    "saved_path": os.path.join(upload_directory, safe_filename),
                                }
                        else:
                            if current_field_name:
                                self.request.body_params[current_field_name].append(form_value)
                        current_field_name = None
                        current_filename = None
                        current_content_type = None
                        form_value = ""

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
            body: The response body, which may be a string, bytes, or generator.
            extra_headers: Optional list of extra header tuples.
        """
        if extra_headers is None:
            extra_headers = []
        status_map: Dict[int, str] = {
            200: "200 OK",
            206: "206 Partial Content",
            302: "302 Found",
            403: "403 Forbidden",
            404: "404 Not Found",
            500: "500 Internal Server Error",
        }
        status_text: str = status_map.get(status_code, f"{status_code} OK")
        sanitized_headers: List[Tuple[str, str]] = []
        for k, v in extra_headers:
            if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
                print(f"Header injection attempt detected: {k}: {v}")
                continue
            sanitized_headers.append((k, v))
        has_content_type: bool = any(h[0].lower() == "content-type" for h in sanitized_headers)
        if not has_content_type:
            sanitized_headers.append(("Content-Type", "text/html; charset=utf-8"))
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (k.encode("latin-1"), v.encode("latin-1")) for k, v in sanitized_headers
            ],
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
        if isinstance(body, str):
            response_body: bytes = body.encode("utf-8")
        elif isinstance(body, bytes):
            response_body = body
        else:
            response_body = str(body).encode("utf-8")
        response_body = body.encode("utf-8") if isinstance(body, str) else body
        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False
        })

    def _cleanup_sessions(self) -> None:
        """
        Clean up expired sessions based on the SESSION_TIMEOUT value.
        """
        now: float = time.time()
        self.sessions = {
            sid: data
            for sid, data in self.sessions.items()
            if data.get("last_access", now) + self.SESSION_TIMEOUT > now
        }

    def _redirect(self, location: str) -> Tuple[int, str]:
        """
        Generate an HTTP redirect response.

        Args:
            location: The URL to redirect to.

        Returns:
            A tuple containing the HTTP status code and the HTML body.
        """
        return (
            302,
            (
                "<html><head>"
                f"<meta http-equiv='refresh' content='0;url={location}'>"
                "</head></html>"
            ),
        )

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
            raise ImportError("`_render_template` not available. Install `jinja2` via pip.")

        def render_sync() -> str:
            assert self.env is not None
            return self.env.get_template(name).render(kwargs)

        return await asyncio.get_event_loop().run_in_executor(None, render_sync)

