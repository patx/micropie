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
from urllib.parse import parse_qs

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA_INSTALLED = True
except ImportError:
    JINJA_INSTALLED = False


class Server:
    """
    A lightweight class providing basic routing, session handling, and
    template rendering using Jinja2 if installed. This class offers both a
    built-in HTTP server mode and a WSGI-compatible application method.
    """

    SESSION_TIMEOUT = 8 * 3600  # 8 hours

    def __init__(self):
        """
        Initialize the Server instance with an optional Jinja2 environment and
        a session store.
        """
        if JINJA_INSTALLED:
            self.env = Environment(loader=FileSystemLoader("templates"))

        self.sessions = {}
        self.query_params = {}
        self.body_params = {}
        self.path_params = []
        self.session = {}
        self.environ = None
        self.start_response = None

    def run(self, host="127.0.0.1", port=8080):
        """
        Use Python's built-in WSGI server (wsgiref) for local development,
        reusing the WSGI app to avoid duplication.
        """
        print(f"Serving on http://{host}:{port}")
        with make_server(host, port, self.wsgi_app) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down server...")

    def get_session(self, request_handler):
        """
        Retrieve or create a session for the current client, setting necessary
        cookies if a new session is created.
        """
        cookie = request_handler.headers.get("Cookie")
        session_id = None

        # Extract session ID from cookies if present
        if cookie:
            cookies = {
                item.split("=")[0].strip(): item.split("=")[1].strip()
                for item in cookie.split(";")
            }
            session_id = cookies.get("session_id")

        # Create a new session if needed
        if not session_id or session_id not in self.sessions:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {"last_access": time.time()}
            request_handler.send_response(200)
            request_handler.send_header(
                "Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict"
            )
            request_handler.end_headers()
            #print(f"New session created: {session_id}")  # DEBUG

        # Update last access
        session = self.sessions.get(session_id)
        if session:
            session["last_access"] = time.time()
        else:
            # Should rarely happen unless manually removed
            session = {"last_access": time.time()}
            self.sessions[session_id] = session

        #print(f"Session data: {session_id} -> {session}") # DEBUG
        return session

    def cleanup_sessions(self):
        """
        Remove sessions not accessed within SESSION_TIMEOUT.
        """
        now = time.time()
        self.sessions = {
            sid: data
            for sid, data in self.sessions.items()
            if data.get("last_access", now) + self.SESSION_TIMEOUT > now
        }

    def redirect(self, location):
        """
        Return a 302 redirect response to the specified location.
        """
        return (
            302,
            (
                "<html><head>"
                f"<meta http-equiv='refresh' content='0;url={location}'>"
                "</head></html>"
            ),
        )

    def render_template(self, name, **kwargs):
        """
        Render a Jinja2 template if jinja2 is installed; otherwise raise
        an ImportError.
        """
        if not JINJA_INSTALLED:
            raise ImportError("Jinja2 is not installed.")
        return self.env.get_template(name).render(kwargs)

    def serve_static(self, filepath):
        """
        Serve a static file securely from the 'static' directory.

        This function ensures that only files within the 'static' directory
        can be served, preventing access to other parts of the filesystem.

        Parameters:
        - filepath: The requested file path relative to the 'static' directory.

        Example usage in route definition:
        def static(self, filename):
            return self.serve_static(filename)
        """
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

    def validate_request(self, method):
        """
        Validate incoming request data for both GET and POST.
        """
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

    def wsgi_app(self, environ, start_response):
        """
        A WSGI-compatible application method that processes incoming requests,
        manages sessions, dispatches to the correct handler function,
        and supports streaming/generator responses.

        IMPORTANT:
          - If your route returns (status, body, extra_headers), we handle them
            in a single call to start_response.
          - Do NOT call `start_response` in your handler.
        """

        # Store environ & start_response on self, if your route needs them
        self.environ = environ
        self.start_response = start_response

        path = environ["PATH_INFO"].strip("/")
        method = environ["REQUEST_METHOD"]

        # Default to "index" if root is accessed
        if not path:
            path = "index"

        # Parse query parameters
        self.query_params = parse_qs(environ["QUERY_STRING"])

        path_parts = path.split("/")
        func_name = path_parts[0]
        self.path_params = path_parts[1:]

        # Mock request handler for session cookies
        class MockRequestHandler:
            def __init__(self, environ):
                self.environ = environ
                self.headers = {
                    key[5:].replace("_", "-").lower(): value
                    for key, value in environ.items()
                    if key.startswith("HTTP_")
                }
                self.cookies = self._parse_cookies()
                self._headers_to_send = []

            def _parse_cookies(self):
                cookies = {}
                if "HTTP_COOKIE" in self.environ:
                    cookie_header = self.environ["HTTP_COOKIE"]
                    for cookie in cookie_header.split(";"):
                        if "=" in cookie:
                            k, v = cookie.strip().split("=", 1)
                            cookies[k] = v
                return cookies

            def send_response(self, code):
                pass  # We'll do final start_response in wsgi_app

            def send_header(self, key, value):
                self._headers_to_send.append((key, value))

            def end_headers(self):
                pass

        request_handler = MockRequestHandler(environ)

        # Ensure session persistence
        session_id = request_handler.cookies.get("session_id")
        if session_id and session_id in self.sessions:
            self.session = self.sessions[session_id]
            self.session["last_access"] = time.time()
            print(f"Using existing session: {session_id}")
        else:
            session_id = str(uuid.uuid4())
            self.session = {"last_access": time.time()}
            self.sessions[session_id] = self.session
            request_handler.send_header(
                "Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Strict;"
            )
            print(f"New session created: {session_id}")

        print(f"Session data: {session_id} -> {self.session}")

        self.request = method
        self.body_params = {}

        # Handle POST body
        if method == "POST":
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
                body = environ["wsgi.input"].read(content_length).decode(
                    "utf-8", "ignore"
                )
                self.body_params = parse_qs(body)
                print("POST data:", self.body_params)
            except Exception as e:
                start_response("400 Bad Request", [("Content-Type", "text/html")])
                return [f"400 Bad Request: {str(e)}".encode("utf-8")]

        # Find the requested handler
        handler_function = getattr(self, func_name, None)
        if not handler_function:
            start_response("404 Not Found", [("Content-Type", "text/html")])
            return [b"404 Not Found"]

        # Build function arguments
        sig = inspect.signature(handler_function)
        func_args = []

        for param in sig.parameters.values():
            if self.path_params:
                func_args.append(self.path_params.pop(0))
            elif param.name in self.query_params:
                func_args.append(self.query_params[param.name][0])
            elif param.name in self.body_params:
                func_args.append(self.body_params[param.name][0])
            elif param.default is not param.empty:
                func_args.append(param.default)
            else:
                msg = f"400 Bad Request: Missing required parameter '{param.name}'"
                start_response("400 Bad Request", [("Content-Type", "text/html")])
                return [msg.encode("utf-8")]

        # Invoke the handler
        try:
            response = handler_function(*func_args)

            # By default, assume 200, no extra headers
            status_code = 200
            response_body = response
            extra_headers = []

            # If the handler returned a tuple, unpack
            if isinstance(response, tuple):
                if len(response) == 2:
                    # (status, body)
                    status_code, response_body = response
                elif len(response) == 3:
                    # (status, body, extra_headers)
                    status_code, response_body, extra_headers = response
                else:
                    start_response("500 Internal Server Error", [("Content-Type", "text/html")])
                    return [b"500 Internal Server Error: Invalid response tuple"]

            # Convert status_code to WSGI status
            status_map = {
                206: "206 Partial Content",
                302: "302 Found",
                404: "404 Not Found",
                500: "500 Internal Server Error",
            }
            status_str = status_map.get(status_code, f"{status_code} OK")

            # Combine final headers
            headers = request_handler._headers_to_send
            headers.extend(extra_headers)

            # Ensure at least one Content-Type header is present
            if not any(h[0].lower() == "content-type" for h in headers):
                headers.append(("Content-Type", "text/html; charset=utf-8"))

            # Call start_response exactly once
            start_response(status_str, headers)

            # If response_body is a generator/iterable, yield pieces
            if hasattr(response_body, "__iter__") and not isinstance(response_body, (bytes, str)):
                def byte_stream(gen):
                    for chunk in gen:
                        if isinstance(chunk, str):
                            yield chunk.encode("utf-8")
                        else:
                            yield chunk
                return byte_stream(response_body)

            # Otherwise, convert str to bytes
            if isinstance(response_body, str):
                response_body = response_body.encode("utf-8")

            return [response_body]

        except Exception as e:
            print(f"Error processing request: {e}")
            # If an exception happened *after* start_response, we can't call it again
            # but we'll try to handle gracefully:
            try:
                start_response("500 Internal Server Error", [("Content-Type", "text/html")])
            except:
                # We may get "headers already set" here, but let's log and ignore
                pass
            return ["500 Internal Server Error:"]

