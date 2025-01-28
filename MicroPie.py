"""
MicroPie: A simple Python ultra-micro web framework with WSGI
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

from wsgiref.simple_server import make_server
import time
import uuid
import inspect
import os
import mimetypes
from urllib.parse import parse_qs
from typing import Optional, Dict, Any, Union, Tuple, List
import asyncio

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA_INSTALLED = True
except ImportError:
    JINJA_INSTALLED = False


class Server:
    SESSION_TIMEOUT: int = 8 * 3600  # 8 hours

    def __init__(self) -> None:
        if JINJA_INSTALLED:
            self.env = Environment(loader=FileSystemLoader("templates"))

        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.query_params: Dict[str, List[str]] = {}
        self.body_params: Dict[str, List[str]] = {}
        self.path_params: List[str] = []
        self.session: Dict[str, Any] = {}
        self.environ: Optional[Dict[str, Any]] = None
        self.start_response: Optional[Any] = None

    def run(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        print(f"Serving on http://{host}:{port}")
        with make_server(host, port, self.wsgi_app) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down server...")

    def get_session(self, request_handler: Any) -> Dict[str, Any]:
        cookie = request_handler.headers.get("Cookie")
        session_id = None

        if cookie:
            cookies = {
                item.split("=")[0].strip(): item.split("=")[1].strip()
                for item in cookie.split(";")
            }
            session_id = cookies.get("session_id")

        if not session_id or session_id not in self.sessions:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {"last_access": time.time()}
            request_handler.send_response(200)
            request_handler.send_header(
                "Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict"
            )
            request_handler.end_headers()

        session = self.sessions.get(session_id)
        if session:
            session["last_access"] = time.time()
        else:
            session = {"last_access": time.time()}
            self.sessions[session_id] = session

        return session

    def cleanup_sessions(self) -> None:
        now = time.time()
        self.sessions = {
            sid: data
            for sid, data in self.sessions.items()
            if data.get("last_access", now) + self.SESSION_TIMEOUT > now
        }

    def redirect(self, location: str) -> Tuple[int, str]:
        return (
            302,
            (
                "<html><head>"
                f"<meta http-equiv='refresh' content='0;url={location}'>"
                "</head></html>"
            ),
        )

    def render_template(self, name: str, **kwargs: Any) -> str:
        if not JINJA_INSTALLED:
            raise ImportError("Jinja2 is not installed.")
        return self.env.get_template(name).render(kwargs)

    def serve_static(self, filepath: str) -> Union[Tuple[int, str], Tuple[int, bytes, List[Tuple[str, str]]]]:
        safe_root = os.path.abspath("static")
        requested_file = os.path.abspath(os.path.join("static", filepath))
        if not requested_file.startswith(safe_root):
            return 403, "403 Forbidden"
        if not os.path.isfile(requested_file):
            return 404, "404 Not Found"
        content_type, _ = mimetypes.guess_type(requested_file)
        if not content_type:
            content_type = "application/octet-stream"
        with open(requested_file, "rb") as f:
            content = f.read()
        return 200, content, [("Content-Type", content_type)]

    def validate_request(self, method: str) -> bool:
        try:
            if method == "GET":
                for key, value in self.query_params.items():
                    if (
                        not isinstance(key, str)
                        or not all(isinstance(v, str) for v in value)
                    ):
                        print(f"Invalid query parameter: {key} -> {value}")
                        return False

            if method == "POST":
                for key, value in self.body_params.items():
                    if (
                        not isinstance(key, str)
                        or not all(isinstance(v, str) for v in value)
                    ):
                        print(f"Invalid body parameter: {key} -> {value}")
                        return False

            return True
        except Exception as e:
            print(f"Error during request validation: {e}")
            return False

    def wsgi_app(self, environ: Dict[str, Any], start_response: Any) -> List[bytes]:
        self.environ = environ
        self.start_response = start_response

        path = environ["PATH_INFO"].strip("/")
        method = environ["REQUEST_METHOD"]

        path_parts = path.split("/") if path else []
        func_name = path_parts[0] if path_parts else "index"
        self.path_params = path_parts[1:] if len(path_parts) > 1 else []

        handler_function = getattr(self, func_name, None)

        if not handler_function:
            self.path_params = path_parts
            handler_function = getattr(self, "index", None)

        self.query_params = parse_qs(environ.get("QUERY_STRING", ""))


        class MockRequestHandler:
            def __init__(self, environ: Dict[str, Any]) -> None:
                self.environ = environ
                self.headers = {
                    key[5:].replace("_", "-").lower(): value
                    for key, value in environ.items()
                    if key.startswith("HTTP_")
                }
                self.cookies = self._parse_cookies()
                self._headers_to_send: List[Tuple[str, str]] = []

            def _parse_cookies(self) -> Dict[str, str]:
                cookies = {}
                if "HTTP_COOKIE" in self.environ:
                    cookie_header = self.environ["HTTP_COOKIE"]
                    for cookie in cookie_header.split(";"):
                        if "=" in cookie:
                            k, v = cookie.strip().split("=", 1)
                            cookies[k] = v
                return cookies

            def send_response(self, code: int) -> None:
                pass

            def send_header(self, key: str, value: str) -> None:
                self._headers_to_send.append((key, value))

            def end_headers(self) -> None:
                pass

        request_handler = MockRequestHandler(environ)

        session_id = request_handler.cookies.get("session_id")
        if session_id and session_id in self.sessions:
            self.session = self.sessions[session_id]
            self.session["last_access"] = time.time()
        else:
            session_id = str(uuid.uuid4())
            self.session = {"last_access": time.time()}
            self.sessions[session_id] = self.session
            request_handler.send_header(
                "Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict;"
            )

        self.request = method
        self.body_params = {}
        self.files = {}

        if method == "POST":
            try:
                content_type = environ.get("CONTENT_TYPE", "")
                content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
                body = environ["wsgi.input"].read(content_length)

                if "multipart/form-data" in content_type:
                    self.parse_multipart(body, content_type)
                else:
                    body_str = body.decode("utf-8", "ignore")
                    self.body_params = parse_qs(body_str)
            except Exception as e:
                start_response("400 Bad Request", [("Content-Type", "text/html")])
                return [f"400 Bad Request: {str(e)}".encode("utf-8")]

        sig = inspect.signature(handler_function)
        func_args = []

        for param in sig.parameters.values():
            if self.path_params:
                func_args.append(self.path_params.pop(0))
            elif param.name in self.query_params:
                func_args.append(self.query_params[param.name][0])
            elif param.name in self.body_params:
                func_args.append(self.body_params[param.name][0])
            elif param.name in self.files:
                func_args.append(self.files[param.name])
            elif param.name in self.session:
                func_args.append(self.session[param.name])
            elif param.default is not param.empty:
                func_args.append(param.default)
            else:
                msg = f"400 Bad Request: Missing required parameter '{param.name}'"
                start_response("400 Bad Request", [("Content-Type", "text/html")])
                return [msg.encode("utf-8")]

        if handler_function == getattr(self, "index", None) and not func_args and path:
            start_response("404 Not Found", [("Content-Type", "text/html")])
            return [b"404 Not Found"]

        try:
            response = handler_function(*func_args)
            status_code = 200
            response_body = response
            extra_headers = []

            if isinstance(response, tuple):
                if len(response) == 2:
                    status_code, response_body = response
                elif len(response) == 3:
                    status_code, response_body, extra_headers = response
                else:
                    start_response("500 Internal Server Error", [("Content-Type", "text/html")])
                    return [b"500 Internal Server Error: Invalid response tuple"]

            status_map = {
                206: "206 Partial Content",
                302: "302 Found",
                404: "404 Not Found",
                500: "500 Internal Server Error",
            }
            status_str = status_map.get(status_code, f"{status_code} OK")
            headers = request_handler._headers_to_send
            headers.extend(extra_headers)
            if not any(h[0].lower() == "content-type" for h in headers):
                headers.append(("Content-Type", "text/html; charset=utf-8"))

            start_response(status_str, headers)

            if hasattr(response_body, "__iter__") and not isinstance(response_body, (bytes, str)):
                def byte_stream(gen: Any) -> Any:
                    for chunk in gen:
                        if isinstance(chunk, str):
                            yield chunk.encode("utf-8")
                        else:
                            yield chunk
                return byte_stream(response_body)

            if isinstance(response_body, str):
                response_body = response_body.encode("utf-8")

            return [response_body]

        except Exception as e:
            print(f"Error processing request: {e}")
            try:
                start_response("500 Internal Server Error", [("Content-Type", "text/html")])
            except:
                pass
            return [b"500 Internal Server Error"]

    def parse_multipart(self, body: bytes, content_type: str) -> None:
        boundary = None
        parts = content_type.split(";")
        for part in parts:
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1]
                break

        if not boundary:
            raise ValueError("Boundary not found in Content-Type header.")

        boundary_bytes = boundary.encode("utf-8")
        delimiter = b'--' + boundary_bytes
        end_delimiter = b'--' + boundary_bytes + b'--'

        sections = body.split(delimiter)
        for section in sections:
            if not section or section == b'--' or section == b'--\r\n':
                continue
            if section.startswith(b'\r\n'):
                section = section[2:]
            if section.endswith(b'\r\n'):
                section = section[:-2]
            if section == b'--':
                continue

            try:
                headers, content = section.split(b'\r\n\r\n', 1)
            except ValueError:
                continue

            headers = headers.decode("utf-8", "ignore").split("\r\n")
            header_dict = {}
            for header in headers:
                if ':' in header:
                    key, value = header.split(':', 1)
                    header_dict[key.strip().lower()] = value.strip()

            disposition = header_dict.get("content-disposition", "")
            disposition_parts = disposition.split(";")
            disposition_dict = {}
            for disp_part in disposition_parts:
                if "=" in disp_part:
                    key, value = disp_part.strip().split("=", 1)
                    disposition_dict[key] = value.strip('"')

            name = disposition_dict.get("name")
            filename = disposition_dict.get("filename")

            if filename:
                file_content_type = header_dict.get("content-type", "application/octet-stream")
                file_data = content
                self.files[name] = {
                    'filename': filename,
                    'content_type': file_content_type,
                    'data': file_data
                }
            elif name:
                value = content.decode("utf-8", "ignore")
                if name in self.body_params:
                    self.body_params[name].append(value)
                else:
                    self.body_params[name] = [value]

class AsyncServer:
    SESSION_TIMEOUT: int = 8 * 3600  # 8 hours

    def __init__(self) -> None:
        if JINJA_INSTALLED:
            self.env = Environment(loader=FileSystemLoader("templates"))

        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.query_params: Dict[str, List[str]] = {}
        self.body_params: Dict[str, List[str]] = {}
        self.path_params: List[str] = []
        self.session: Dict[str, Any] = {}
        self.files: Dict[str, Any] = {}

    async def __call__(self, scope, receive, send):
        await self.asgi_app(scope, receive, send)

    async def asgi_app(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        """ASGI application entrypoint for both HTTP and WebSockets."""

        if scope["type"] == "websocket":
            # Example approach for route-based WebSocket handler lookup:
            path = scope["path"].lstrip("/")
            path_parts = path.split("/") if path else []
            func_name = path_parts[0] if path_parts else "default"
            self.path_params = path_parts[1:] if len(path_parts) > 1 else []

            # Use a naming convention such as websocket_<func_name>.
            ws_handler_name = f"websocket_{func_name}"
            handler_function = getattr(self, ws_handler_name, None)

            if not handler_function:
                await self._websocket_default(scope, receive, send)
                return

            try:
                await handler_function(scope, receive, send)
            except Exception:
                await send({"type": "websocket.close", "code": 1011})
            return

        elif scope["type"] == "http":
            method = scope["method"]
            path = scope["path"].lstrip("/")
            path_parts = path.split("/") if path else []
            func_name = path_parts[0] if path_parts else "index"
            self.path_params = path_parts[1:] if len(path_parts) > 1 else []

            handler_function = getattr(self, func_name, None)
            if not handler_function:
                self.path_params = path_parts
                handler_function = getattr(self, "index", None)

            raw_query = scope.get("query_string", b"")
            self.query_params = parse_qs(raw_query.decode("utf-8", "ignore"))

            headers_dict = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }
            cookies = self._parse_cookies(headers_dict.get("cookie", ""))

            session_id = cookies.get("session_id")
            if session_id and session_id in self.sessions:
                self.session = self.sessions[session_id]
                self.session["last_access"] = time.time()
            else:
                session_id = str(uuid.uuid4())
                self.session = {"last_access": time.time()}
                self.sessions[session_id] = self.session

            self.body_params = {}
            self.files = {}
            if method in ("POST", "PUT", "PATCH"):
                body_data = bytearray()
                while True:
                    msg = await receive()
                    if msg["type"] == "http.request":
                        body_data += msg.get("body", b"")
                        if not msg.get("more_body"):
                            break
                content_type = headers_dict.get("content-type", "")
                if "multipart/form-data" in content_type:
                    self.parse_multipart(bytes(body_data), content_type)
                else:
                    body_str = body_data.decode("utf-8", "ignore")
                    self.body_params = parse_qs(body_str)

            sig = inspect.signature(handler_function)
            func_args = []
            for param in sig.parameters.values():
                if self.path_params:
                    func_args.append(self.path_params.pop(0))
                elif param.name in self.query_params:
                    func_args.append(self.query_params[param.name][0])
                elif param.name in self.body_params:
                    func_args.append(self.body_params[param.name][0])
                elif param.name in self.files:
                    func_args.append(self.files[param.name])
                elif param.name in self.session:
                    func_args.append(self.session[param.name])
                elif param.default is not param.empty:
                    func_args.append(param.default)
                else:
                    await self._send_response(
                        send,
                        status_code=400,
                        body=f"400 Bad Request: Missing required parameter '{param.name}'",
                    )
                    return

            if handler_function == getattr(self, "index", None) and not func_args and path:
                await self._send_response(send, status_code=404, body="404 Not Found")
                return

            try:
                if inspect.iscoroutinefunction(handler_function):
                    result = await handler_function(*func_args)
                else:
                    result = handler_function(*func_args)
            except Exception as e:
                print(f"Error processing request: {e}")
                await self._send_response(
                    send, status_code=500, body="500 Internal Server Error"
                )
                return

            status_code = 200
            response_body = result
            extra_headers: List[Tuple[str, str]] = []

            if isinstance(result, tuple):
                if len(result) == 2:
                    status_code, response_body = result
                elif len(result) == 3:
                    status_code, response_body, extra_headers = result
                else:
                    await self._send_response(
                        send, status_code=500,
                        body="500 Internal Server Error: Invalid response tuple"
                    )
                    return

            session_cookie_header = (
                "Set-Cookie",
                f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict"
            )
            has_session_cookie = any(
                h[0].lower() == "set-cookie" and "session_id=" in h[1]
                for h in extra_headers
            )
            if not has_session_cookie:
                extra_headers.append(session_cookie_header)

            await self._send_response(
                send,
                status_code=status_code,
                body=response_body,
                extra_headers=extra_headers
            )

    async def _websocket_default(self, scope: Dict[str, Any], receive: Any, send: Any):
        """Default WebSocket handler if no match is found."""
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 1000})

    def _parse_cookies(self, cookie_header: str) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        if not cookie_header:
            return cookies
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                k, v = cookie.strip().split("=", 1)
                cookies[k] = v
        return cookies

    def parse_multipart(self, body: bytes, content_type: str) -> None:
        boundary = None
        parts = content_type.split(";")
        for part in parts:
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1]
                break

        if not boundary:
            raise ValueError("Boundary not found in Content-Type header.")

        boundary_bytes = boundary.encode("utf-8")
        delimiter = b"--" + boundary_bytes
        sections = body.split(delimiter)
        for section in sections:
            if not section or section in (b"--", b"--\r\n"):
                continue
            if section.startswith(b"\r\n"):
                section = section[2:]
            if section.endswith(b"\r\n"):
                section = section[:-2]
            if section == b"--":
                continue

            try:
                headers, content = section.split(b"\r\n\r\n", 1)
            except ValueError:
                continue

            headers_list = headers.decode("utf-8", "ignore").split("\r\n")
            header_dict = {}
            for header_line in headers_list:
                if ":" in header_line:
                    key, value = header_line.split(":", 1)
                    header_dict[key.strip().lower()] = value.strip()

            disposition = header_dict.get("content-disposition", "")
            disposition_parts = disposition.split(";")
            disposition_dict = {}
            for disp_part in disposition_parts:
                if "=" in disp_part:
                    k, v = disp_part.strip().split("=", 1)
                    disposition_dict[k] = v.strip('"')

            name = disposition_dict.get("name")
            filename = disposition_dict.get("filename")

            if filename:
                file_content_type = header_dict.get("content-type", "application/octet-stream")
                self.files[name] = {
                    "filename": filename,
                    "content_type": file_content_type,
                    "data": content
                }
            elif name:
                value = content.decode("utf-8", "ignore")
                if name in self.body_params:
                    self.body_params[name].append(value)
                else:
                    self.body_params[name] = [value]

    async def _send_response(
        self,
        send: Any,
        status_code: int,
        body: Union[str, bytes, Any],
        extra_headers: List[Tuple[str, str]] = None
    ) -> None:
        if extra_headers is None:
            extra_headers = []

        status_map = {
            200: "200 OK",
            206: "206 Partial Content",
            302: "302 Found",
            403: "403 Forbidden",
            404: "404 Not Found",
            500: "500 Internal Server Error",
        }
        status_text = status_map.get(status_code, f"{status_code} OK")

        has_content_type = any(h[0].lower() == "content-type" for h in extra_headers)
        if not has_content_type:
            extra_headers.append(("Content-Type", "text/html; charset=utf-8"))

        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (k.encode("latin-1"), v.encode("latin-1")) for k, v in extra_headers
            ],
        })

        response_body = b""
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, str)):
            for chunk in body:
                if isinstance(chunk, str):
                    response_body += chunk.encode("utf-8")
                else:
                    response_body += chunk
        else:
            if isinstance(body, str):
                response_body = body.encode("utf-8")
            elif isinstance(body, bytes):
                response_body = body
            else:
                response_body = str(body).encode("utf-8")

        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False,
        })

    def cleanup_sessions(self) -> None:
        now = time.time()
        self.sessions = {
            sid: data
            for sid, data in self.sessions.items()
            if data.get("last_access", now) + self.SESSION_TIMEOUT > now
        }

    def redirect(self, location: str) -> Tuple[int, str]:
        return (
            302,
            (
                "<html><head>"
                f"<meta http-equiv='refresh' content='0;url={location}'>"
                "</head></html>"
            ),
        )

    def render_template(self, name: str, **kwargs: Any) -> str:
        if not JINJA_INSTALLED:
            raise ImportError("Jinja2 is not installed.")
        return self.env.get_template(name).render(kwargs)

    def serve_static(
        self, filepath: str
    ) -> Union[Tuple[int, str], Tuple[int, bytes, List[Tuple[str, str]]]]:
        safe_root = os.path.abspath("static")
        requested_file = os.path.abspath(os.path.join("static", filepath))
        if not requested_file.startswith(safe_root):
            return 403, "403 Forbidden"
        if not os.path.isfile(requested_file):
            return 404, "404 Not Found"
        content_type, _ = mimetypes.guess_type(requested_file)
        if not content_type:
            content_type = "application/octet-stream"
        with open(requested_file, "rb") as f:
            content = f.read()
        return 200, content, [("Content-Type", content_type)]

    def validate_request(self, method: str) -> bool:
        try:
            if method == "GET":
                for key, value in self.query_params.items():
                    if (
                        not isinstance(key, str)
                        or not all(isinstance(v, str) for v in value)
                    ):
                        return False

            if method == "POST":
                for key, value in self.body_params.items():
                    if (
                        not isinstance(key, str)
                        or not all(isinstance(v, str) for v in value)
                    ):
                        return False

            return True
        except:
            return False

