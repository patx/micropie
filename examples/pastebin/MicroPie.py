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

        self.query_params = parse_qs(environ["QUERY_STRING"])

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
