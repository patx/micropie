"""
MicroPie: A simple and lightweight Python micro web framework w/ WSGI support
https://patx.github.io/micropie
"""

import http.server
import socketserver
from urllib.parse import parse_qs
import time
import uuid
import inspect
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader


class Server:
    """
    A lightweight server class providing basic routing, session handling, and
    template rendering using Jinja2. This class uses an internally defined
    request handler to manage GET and POST requests.
    """

    SESSION_TIMEOUT = 8 * 3600  # 8 hours

    def __init__(self):
        """
        Initialize the Server instance with default settings, Jinja2 environment,
        and session storage.
        """
        self.handlers = {}
        self.env = Environment(loader=FileSystemLoader("templates"))
        self.sessions = {}

    def run(self, host="127.0.0.1", port=8080):
        """
        Start the HTTP server, binding it to the specified host and port.

        :param host: The hostname or IP address to bind the server to.
        :param port: The port number to listen on.
        """

        class DynamicRequestHandler(http.server.SimpleHTTPRequestHandler):
            """
            A dynamically generated request handler that uses the Server instance
            for routing and request processing.
            """

            def do_GET(self):
                """
                Handle GET requests by dispatching to the appropriate server
                method.
                """
                self._handle_request("GET")

            def do_POST(self):
                """
                Handle POST requests by dispatching to the appropriate server
                method.
                """
                self._handle_request("POST")

            def _handle_request(self, method):
                """
                Main request handling method that parses the URL path, queries
                the Server instance to find the appropriate function, and invokes
                it with the correct arguments.

                :param method: The HTTP method (GET or POST) used for this request.
                """
                instance = self.server.instance

                parsed_path = urlparse(self.path)
                path_parts = parsed_path.path.strip("/").split("/")
                func_name = path_parts[0] or "index"
                func = getattr(instance, func_name, None)

                if func:
                    instance.session = instance.get_session(self)
                    instance.request = method
                    instance.query_params = parse_qs(parsed_path.query)
                    instance.path_params = path_parts[1:]
                    instance.body_params = {}

                    if method == "POST":
                        content_length = int(
                            self.headers.get("Content-Length", 0)
                        )
                        body = self.rfile.read(content_length).decode("utf-8")
                        instance.body_params = parse_qs(body)

                    if not instance.validate_request(method):
                        self.send_error(400, "Invalid Request")
                        return

                    try:
                        func_args = self._get_func_args(
                            func,
                            instance.query_params,
                            instance.body_params,
                            instance.path_params,
                            method
                        )
                        response = func(*func_args)
                        self._send_response(response)
                    except Exception as e:
                        print(f"Error handling request: {e}")
                        self.send_error(500, f"Internal Server Error: {e}")
                else:
                    self.send_error(404, "Not Found")

            def _get_func_args(self, func, query_params, body_params,
                               path_params, method):
                """
                Build the argument list for the function being invoked based on
                the function's signature, path parameters, query parameters,
                and body parameters.

                :param func: The function (endpoint) to be invoked.
                :param query_params: A dictionary of query parameters for GET requests.
                :param body_params: A dictionary of body parameters for POST requests.
                :param path_params: Remaining path segments for dynamic URL segments.
                :param method: The HTTP method (GET or POST) used for this request.
                :return: A list of arguments to pass to the function.
                """
                sig = inspect.signature(func)
                args = []
                for param in sig.parameters.values():
                    if path_params:
                        args.append(path_params.pop(0))
                    elif method == "GET" and param.name in query_params:
                        args.append(query_params[param.name][0])
                    elif method == "POST" and param.name in body_params:
                        args.append(body_params[param.name][0])
                    elif param.default is not param.empty:
                        args.append(param.default)
                    else:
                        raise ValueError(
                            f"Missing required parameter: {param.name}"
                        )
                return args

            def _send_response(self, response):
                """
                Send the appropriate HTTP response back to the client based on
                the content returned by the handler function.

                :param response: The content returned by the handler function. Can
                                be a string or a (status_code, body) tuple.
                """
                try:
                    if isinstance(response, str):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(response.encode("utf-8"))
                    elif isinstance(response, tuple) and len(response) == 2:
                        status, body = response
                        self.send_response(status)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(body.encode("utf-8"))
                    else:
                        self.send_error(500, "Invalid response format")
                except Exception as e:
                    print(f"Error sending response: {e}")
                    self.send_error(500, f"Internal Server Error: {e}")

        handler = DynamicRequestHandler

        with socketserver.TCPServer((host, port), handler) as httpd:
            httpd.instance = self
            print(f"Serving on {host}:{port}")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down...")

    def get_session(self, request_handler):
        """
        Retrieve the session for the current client, creating one if necessary.

        :param request_handler: The request handler instance managing the current
                                request. Used to read and set cookies.
        :return: The session dictionary associated with the current client.
        """
        cookie = request_handler.headers.get('Cookie')
        session_id = None

        # Extract session ID from cookies
        if cookie:
            cookies = {
                item.split('=')[0].strip(): item.split('=')[1].strip()
                for item in cookie.split(';')
            }
            session_id = cookies.get('session_id')

        # Create a new session if one doesn't exist
        if not session_id or session_id not in self.sessions:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {"last_access": time.time()}
            request_handler.send_response(200)
            request_handler.send_header('Set-Cookie', f'session_id={session_id}; Path=/')
            request_handler.end_headers()
            print(f"New session created: {session_id}")

        # Update session last access time (reset timeout)
        session = self.sessions.get(session_id)
        if session:
            session['last_access'] = time.time()
        else:
            print("Session unexpectedly missing, creating a new one.")
            session = {"last_access": time.time()}
            self.sessions[session_id] = session

        print(f"Session data: {session_id} -> {session}")
        return session

    def cleanup_sessions(self):
        """
        Clean up expired sessions by removing those that have not been accessed
        within the SESSION_TIMEOUT period.
        """
        now = time.time()
        self.sessions = {
            sid: data for sid, data in self.sessions.items()
            if data.get('last_access', now) + self.SESSION_TIMEOUT > now
        }

    def redirect(self, location):
        """
        Return a 302 redirect response to the specified location.

        :param location: The URL or path to redirect the client to.
        :return: A tuple containing the HTTP status code (302) and a minimal
                 HTML document that redirects to the given location.
        """
        return (
            302,
            f"<html><head><meta http-equiv='refresh' content='0;url={location}'></head></html>"
        )

    def render_template(self, name, **args):
        """
        Render a Jinja2 template by name, passing in any additional arguments
        as template variables.

        :param name: The name of the template file to render.
        :param args: Additional keyword arguments to pass to the template.
        :return: The rendered template as a string.
        """
        return self.env.get_template(name).render(args)

    def validate_request(self, method):
        """
        Validate incoming request data for both GET and POST methods.

        :param method: The HTTP method of the current request.
        :return: True if all parameters are valid, False otherwise.
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
        WSGI-compatible application wrapper for running MicroPie apps with Gunicorn or other WSGI servers.

        :param environ: WSGI environment dictionary.
        :param start_response: WSGI start_response function.
        """
        path = environ['PATH_INFO'].strip("/")
        method = environ['REQUEST_METHOD']

        # Default to index if root is accessed
        if not path:
            path = "index"

        # Parse query parameters
        self.query_params = parse_qs(environ['QUERY_STRING'])

        # Split the path to extract potential parameters
        path_parts = path.split('/')

        # Determine the function name from path, default to index
        func_name = path_parts[0] if path_parts[0] else "index"

        # Assign request properties to app
        self.request = method
        self.path_params = path_parts[1:]  # Exclude the function name

        # Handle POST request body
        if method == "POST":
            try:
                content_length = int(environ.get('CONTENT_LENGTH', 0))
                body = environ['wsgi.input'].read(content_length) if content_length > 0 else b""
                post_params = parse_qs(body.decode('utf-8'))
                self.body_params = {k: v[0] for k, v in post_params.items()}
            except Exception as e:
                start_response('400 Bad Request', [('Content-Type', 'text/html')])
                return [f"400 Bad Request: {str(e)}".encode('utf-8')]
        else:
            self.body_params = {}

        try:
            # Find the function to call or return 404 if not found
            handler_function = getattr(self, func_name, None)
            if handler_function:
                # Get function signature to determine required arguments
                sig = inspect.signature(handler_function)
                func_args = []

                for param in sig.parameters.values():
                    if self.path_params:
                        func_args.append(self.path_params.pop(0))
                    elif param.name in self.query_params:
                        func_args.append(self.query_params[param.name][0])
                    elif param.name in self.body_params:
                        func_args.append(self.body_params[param.name])
                    elif param.default is not param.empty:
                        func_args.append(param.default)
                    else:
                        start_response('400 Bad Request', [('Content-Type', 'text/html')])
                        return [f"400 Bad Request: Missing required parameter '{param.name}'".encode('utf-8')]

                # Call the handler with the parameters
                response = handler_function(*func_args)

                # Handle tuple (status, body) response
                if isinstance(response, tuple) and len(response) == 2:
                    status, body = response
                    status = f"{status} Found" if status == 302 else f"{status} OK"
                else:
                    status, body = '200 OK', response

                start_response(status, [('Content-Type', 'text/html')])
                return [body.encode('utf-8')]
            else:
                start_response('404 Not Found', [('Content-Type', 'text/html')])
                return [b'404 Not Found']

        except Exception as e:
            if not environ.get('gunicorn.error_handled'):
                start_response('500 Internal Server Error', [('Content-Type', 'text/html')])
            environ['gunicorn.error_handled'] = True
            return [f"500 Internal Server Error: {str(e)}".encode('utf-8')]

