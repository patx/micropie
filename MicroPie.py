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
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_INSTALLED = True
except ImportError:
    JINJA_INSTALLED = False

try:
    from multipart import PushMultipartParser, MultipartSegment
    import aiofiles, aiofiles.os
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
        """Load session data given a session ID."""
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
# Middleware Abstraction
# -----------------------------
class HttpMiddleware(ABC):
    """
    Pluggable middleware class that allows hooking into the request lifecycle.
    """

    @abstractmethod
    async def before_request(self, request: "Request") -> None:
        """
        Called before the request is processed.
        """
        pass

    @abstractmethod
    async def after_request(
        self,
        request: "Request",
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> None:
        """
        Called after the request is processed, but before the final response
        is sent to the client. You may alter the status_code, response_body,
        or extra_headers if needed.
        """
        pass


# -----------------
# Request Object
# -----------------
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


# -----------------
# Application Base
# -----------------
class App:
    """
    ASGI application for handling HTTP requests in MicroPie.
    It supports pluggable session backends via the 'session_backend' attribute
    and pluggable middlewares via the 'middlewares' list.
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

        # Register the session backend: default to in-memory if none provided.
        self.session_backend: SessionBackend = session_backend or InMemorySessionBackend()

        # A list of middleware instances implementing the HttpMiddleware ABC.
        self.middlewares: List[HttpMiddleware] = []

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
        # Entry point remains the same: handle HTTP or other scope types
        if scope["type"] == "http":
            await self._handle_asgi_http(scope, receive, send)
        else:
            # For non-HTTP scopes, do nothing or handle websockets, etc., as needed
            pass

    async def _handle_asgi_http(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Handle the main HTTP request logic."""
        request: Request = Request(scope)
        token = current_request.set(request)
        status_code: int = 200
        response_body: Any = ""
        extra_headers: List[Tuple[str, str]] = []

        try:
            early_return_data = await self._run_middlewares_before(request)
            if early_return_data is not None:
                # If a middleware returns data, it means we should respond immediately
                await self._send_response(
                    send,
                    early_return_data["status_code"],
                    early_return_data["body"],
                    early_return_data.get("headers", [])
                )
                return

            status_code, response_body, extra_headers = await self._prepare_request(request, receive, send)

            # Prepare and invoke handler if we didn't already handle an error or short-return
            if status_code < 400 or (status_code == 404 and response_body == "404 Not Found"):
                # 404 is still valid for handler attempts if we found none
                status_code, response_body, extra_headers = await self._invoke_handler(
                    request, status_code, response_body, extra_headers, send
                )

            # Run after_request middleware
            after_data = await self._run_middlewares_after(request, status_code, response_body, extra_headers)
            if after_data is not None:
                status_code = after_data.get("status_code", status_code)
                response_body = after_data.get("body", response_body)
                extra_headers = after_data.get("headers", extra_headers)

            await self._send_response(send, status_code, response_body, extra_headers)

        finally:
            current_request.reset(token)

    async def _run_middlewares_before(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Run the before_request hook for each middleware. If any returns data,
        we should respond immediately.
        """
        for mw in self.middlewares:
            result = await mw.before_request(request)
            if result is not None:
                return result
        return None

    async def _run_middlewares_after(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Run the after_request hook for each middleware. If any returns data,
        use it to override status, body, or headers.
        """
        for mw in self.middlewares:
            result = await mw.after_request(request, status_code, response_body, extra_headers)
            if result is not None:
                status_code = result.get("status_code", status_code)
                response_body = result.get("body", response_body)
                extra_headers = result.get("headers", extra_headers)
        return None

    async def _prepare_request(
        self,
        request: Request,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> Tuple[int, Any, List[Tuple[str, str]]]:
        """
        Prepare the request object by parsing query params, cookies, and session,
        and load body content if there's any (POST, PUT, PATCH).
        """
        status_code = 200
        response_body: Any = ""
        extra_headers: List[Tuple[str, str]] = []

        method: str = request.method
        path: str = request.scope["path"].lstrip("/")
        path_parts: List[str] = path.split("/") if path else []
        request.path_params = path_parts[1:] if len(path_parts) > 1 else []

        raw_query: bytes = request.scope.get("query_string", b"")
        request.query_params = parse_qs(raw_query.decode("utf-8", "ignore"))

        # Parse headers and cookies
        headers_dict: Dict[str, str] = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in request.scope.get("headers", [])
        }
        cookies: Dict[str, str] = self._parse_cookies(headers_dict.get("cookie", ""))

        # Load session
        session_cookie = "session_id"
        session_id: Optional[str] = cookies.get(session_cookie)
        if session_id:
            request.session = await self.session_backend.load(session_id)
        else:
            request.session = {}

        if method in ("POST", "PUT", "PATCH"):
            parse_result = await self._process_request_body(request, headers_dict, receive, send)
            if isinstance(parse_result, tuple) and parse_result[0] >= 400:
                return parse_result  # e.g. (400, "Bad Request", ...)

        return status_code, response_body, extra_headers

    async def _process_request_body(
        self,
        request: Request,
        headers_dict: Dict[str, str],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> Tuple[int, str, List[Tuple[str, str]]]:
        """
        Read and parse the request body for form data or multipart data.
        Returns an error tuple if something fails; otherwise (200, "", []).
        """
        body_data = bytearray()
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
                return 400, "400 Bad Request: Boundary not found in Content-Type header", []
            boundary: bytes = match.group(1).encode("utf-8")
            reader: asyncio.StreamReader = asyncio.StreamReader()
            reader.feed_data(body_data)
            reader.feed_eof()
            parse_res = await self._parse_multipart(reader, boundary)
            if isinstance(parse_res, tuple) and parse_res[0] == 500:
                return parse_res  # e.g. (500, "Server Error")
        else:
            body_str: str = body_data.decode("utf-8", "ignore")
            request.body_params = parse_qs(body_str)
        return 200, "", []

    async def _invoke_handler(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> Tuple[int, Any, List[Tuple[str, str]]]:
        """
        Find and invoke the correct handler function based on the path,
        then assemble the final response or error if needed.
        """
        path: str = request.scope["path"].lstrip("/")
        path_parts: List[str] = path.split("/") if path else []
        func_name: str = path_parts[0] if path_parts else "index"

        # Disallow calling methods starting with underscore
        if func_name.startswith("_"):
            return 404, "404 Not Found", extra_headers

        # Attempt to look up a handler on the App instance
        handler_function: Optional[Callable[..., Any]] = getattr(self, func_name, None)
        if not handler_function:
            request.path_params = path_parts
            handler_function = getattr(self, "index", None)
            if not handler_function:
                return 404, "404 Not Found", extra_headers

        # If we found a valid handler, gather arguments from request
        try:
            prepared_args = await self._extract_params(handler_function, request, send)
        except Tuple as error_tuple:
            # If we used error-based short circuit (like 400 missing param)
            return error_tuple  # type: ignore
        except Exception as e:
            print(f"Error processing request: {e}")
            return 500, "500 Internal Server Error", extra_headers

        # If a path was specified and matched the index function with no args, still 404
        if handler_function == getattr(self, "index", None) and not prepared_args and path:
            return 404, "404 Not Found", extra_headers

        # Call the handler
        try:
            if inspect.iscoroutinefunction(handler_function):
                result = await handler_function(*prepared_args)
            else:
                result = handler_function(*prepared_args)
        except Exception as e:
            print(f"Error processing request: {e}")
            return 500, "500 Internal Server Error", extra_headers

        # Process the return value
        final_code, final_body, final_headers = self._handle_response(result, status_code, response_body, extra_headers)

        # Save session if it exists
        if request.session:
            session_cookie = "session_id"
            cookies: Dict[str, str] = {
                h[1].split("=")[0]: h[1].split("=")[1]
                for h in final_headers if h[0].lower() == "set-cookie"
            }
            session_id = cookies.get(session_cookie)
            if not session_id:
                session_id = str(uuid.uuid4())
                final_headers.append(
                    ("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict")
                )
            asyncio.create_task(self.session_backend.save(session_id, request.session, SESSION_TIMEOUT))

        return final_code, final_body, final_headers

    async def _extract_params(
        self,
        handler_function: Callable[..., Any],
        request: Request,
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> List[Any]:
        """
        Build function arguments from path, query, body, files, and session values.
        Raises an exception or returns a tuple (status_code, message, headers) on error.
        """
        sig = inspect.signature(handler_function)
        func_args: List[Any] = []

        for param in sig.parameters.values():
            param_value = None
            if request.path_params:
                param_value = request.path_params.pop(0)
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
                # Missing required parameter
                raise Exception((400, f"400 Bad Request: Missing required parameter '{param.name}'", []))

            func_args.append(param_value)
        return func_args

    def _handle_response(
        self,
        result: Any,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]]
    ) -> Tuple[int, Any, List[Tuple[str, str]]]:
        """
        Interpret the result returned by the handler and convert
        it into (status_code, body, headers).
        """
        final_code = status_code
        final_body = response_body
        final_headers = extra_headers[:]

        if isinstance(result, tuple):
            if len(result) == 2:
                final_code, final_body = result
            elif len(result) == 3:
                final_code, final_body, final_headers = result
            else:
                return 500, "500 Internal Server Error: Invalid response tuple", final_headers
        else:
            final_body = result

        return final_code, final_body, final_headers

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

    async def _parse_multipart(self, reader: asyncio.StreamReader, boundary: bytes):
        """
        Parse multipart/form-data from the given reader using the specified boundary.

        Args:
            reader: An asyncio.StreamReader containing the multipart data.
            boundary: The boundary bytes extracted from the Content-Type header.

        Returns:
            None or a (status_code, error_message) tuple on error.
        """
        if not MULTIPART_INSTALLED:
            print("For multipart form data support install 'multipart' and 'aiofiles'.")
            return 500, "500 Internal Server Error"

        with PushMultipartParser(boundary) as parser:
            current_field_name: Optional[str] = None
            current_filename: Optional[str] = None
            current_content_type: Optional[str] = None
            current_file: Optional[Any] = None
            form_value: str = ""
            upload_directory: str = "uploads"
            await aiofiles.os.makedirs(upload_directory, exist_ok=True)
            while not parser.closed:
                try:
                    chunk: bytes = await reader.read(65536)
                except Exception as e:
                    print(f"Error reading multipart data: {e}")
                    return 500, "500 Internal Server Error"
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
                            safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", safe_filename)
                            file_path: str = os.path.join(upload_directory, safe_filename)
                            current_file = await aiofiles.open(file_path, "wb")
                        else:
                            if current_field_name not in self.request.body_params:
                                self.request.body_params[current_field_name] = []
                    elif result:
                        if current_file:
                            await current_file.write(result)
                        else:
                            form_value += result.decode("utf-8", "ignore")
                    else:
                        if current_file:
                            await current_file.close()
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

        # Sanitize headers
        sanitized_headers: List[Tuple[str, str]] = []
        for k, v in extra_headers:
            if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
                print(f"Header injection attempt detected: {k}: {v}")
                continue
            sanitized_headers.append((k, v))

        # Ensure Content-Type
        if not any(h[0].lower() == "content-type" for h in sanitized_headers):
            sanitized_headers.append(("Content-Type", "text/html; charset=utf-8"))

        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in sanitized_headers],
        })

        if hasattr(body, "__aiter__"):
            # For async generator
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
            # For normal generator
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

        # For string or bytes
        response_body = (body if isinstance(body, bytes)
                         else str(body).encode("utf-8"))
        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False
        })

    def _redirect(self, location: str) -> Tuple[int, str]:
        """
        Generate an HTTP redirect response.

        Args:
            location: The URL to redirect to.

        Returns:
            A tuple containing the HTTP status code and the HTML body.
        """
        return 302, "", [("Location", location)]

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
            return "500 Internal Server Error"
        assert self.env is not None
        template = await asyncio.to_thread(self.env.get_template, name)
        return await template.render_async(**kwargs)
