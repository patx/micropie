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
import inspect
import mimetypes
import os
import time
from typing import Optional, Dict, Any, Union, Tuple, List
from urllib.parse import parse_qs
import uuid

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA_INSTALLED = True
    import asyncio
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
        self.files: Dict[str, Any] = {}

    async def __call__(self, scope, receive, send):
        await self.asgi_app(scope, receive, send)

    async def asgi_app(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        """ASGI application entrypoint for both HTTP and WebSockets."""

        if scope["type"] == "http":
            self.scope = scope
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
                self.session = {}

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

            if self.session:
                session_id = cookies.get("session_id", str(uuid.uuid4()))
                self.sessions[session_id] = self.session  # Store session only if used
                extra_headers.append(("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict"))

            await self._send_response(
                send,
                status_code=status_code,
                body=response_body,
                extra_headers=extra_headers
            )
        else:
            pass

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
        send,
        status_code: int,
        body,
        extra_headers=None
    ):
        if extra_headers is None:
            extra_headers = []

        # Common HTTP status text
        status_map = {
            200: "200 OK",
            206: "206 Partial Content",
            302: "302 Found",
            403: "403 Forbidden",
            404: "404 Not Found",
            500: "500 Internal Server Error",
        }
        # Fallback if not in map
        status_text = status_map.get(status_code, f"{status_code} OK")

        # Ensure there's a Content-Type unless already provided
        has_content_type = any(h[0].lower() == "content-type" for h in extra_headers)
        if not has_content_type:
            extra_headers.append(("Content-Type", "text/html; charset=utf-8"))

        # Send the initial response start
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (k.encode("latin-1"), v.encode("latin-1")) for k, v in extra_headers
            ],
        })

        # 1) Check if body is an async generator (has __aiter__)
        if hasattr(body, "__aiter__"):
            async for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            # Send a final empty chunk to mark the end
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False
            })
            return

        # 2) Check if body is a *sync* generator (has __iter__) and
        #    is not a plain string/bytes
        if hasattr(body, "__iter__") and not isinstance(body, (bytes, str)):
            for chunk in body:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            # Send a final empty chunk
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False
            })
            return

        if isinstance(body, str):
            response_body = body.encode("utf-8")
        elif isinstance(body, bytes):
            response_body = body
        else:
            # Convert anything else to string then to bytes
            response_body = str(body).encode("utf-8")

        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False
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

    async def render_template(self, name: str, **kwargs: Any) -> str:
        """
        Async-compatible template rendering using Jinja2.
        """
        if not JINJA_INSTALLED:
            raise ImportError("Jinja2 is not installed.")

        def render_sync():
            return self.env.get_template(name).render(kwargs)

        return await asyncio.get_event_loop().run_in_executor(None, render_sync)

