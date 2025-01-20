import unittest
import uuid
import time
from io import BytesIO
from unittest.mock import patch
from MicroPie import Server


class TestMicroPie(unittest.TestCase):
    def setUp(self):
        """
        Create a fresh instance of the Server for each test and define some
        sample endpoints on the fly.
        """
        self.server = Server()

        # Define a simple default endpoint
        def index():
            return "Hello from index!"

        # Define an endpoint that greets the user by name
        def greet(name="World"):
            return f"Hello, {name}!"

        # Define an endpoint that triggers a redirect
        def go_away():
            return self.server.redirect("/gone")

        # Define an endpoint for testing template rendering (requires a
        # templates/greet.html file in your project for a real test).
        def greet_template(name="World"):
            return self.server.render_template("greet.html", name=name)

        # Attach the functions to the server instance
        self.server.index = index
        self.server.greet = greet
        self.server.go_away = go_away
        self.server.greet_template = greet_template

    def _start_response(self, status, headers):
        """
        Helper method to capture the status and headers from wsgi_app calls.
        """
        self._wsgi_status = status
        self._wsgi_headers = headers

    def test_index_get(self):
        """
        Ensure that accessing '/' via GET calls the 'index' function and
        returns the correct body.
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",           # Access root
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "200 OK")
        self.assertIn("Hello from index!", body)

    def test_custom_endpoint_get(self):
        """
        Ensure that a custom endpoint (greet) can accept query parameters
        through GET and return the correct response.
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/greet",
            "QUERY_STRING": "name=Alice",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "200 OK")
        self.assertIn("Hello, Alice!", body)

    def test_custom_endpoint_path_param(self):
        """
        Test that path parameters are used if present. For example, accessing
        '/greet/Bob' should call greet("Bob").
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/greet/Bob",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "200 OK")
        self.assertIn("Hello, Bob!", body)

    def test_endpoint_not_found(self):
        """
        Access a path that does not map to a defined method. Expect 404.
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/does_not_exist",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "404 Not Found")
        self.assertIn("404 Not Found", body)

    def test_post_request(self):
        """
        Test handling of a POST request with form data in the body.
        """
        post_body = "name=Charlie"
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/greet",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(post_body.encode("utf-8")),
            "CONTENT_LENGTH": str(len(post_body)),
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "200 OK")
        self.assertIn("Hello, Charlie!", body)

    def test_redirect(self):
        """
        Test that an endpoint can return a 302 redirect.
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/go_away",   # Calls the go_away function
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        # MicroPie returns (302, <html>...) so we expect status to be "302 Found"
        self.assertEqual(self._wsgi_status, "302 Found")
        self.assertIn("url=/gone", body)   # Basic check that the redirect body is correct

    def test_session_creation(self):
        """
        Test that a session is created if no session cookie is present.
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            # No HTTP_COOKIE -> expect new session
        }
        response = self.server.wsgi_app(environ, self._start_response)
        _ = b"".join(response).decode()

        # Find the Set-Cookie header among the WSGI headers
        set_cookie_headers = [h for h in self._wsgi_headers if h[0] == 'Set-Cookie']
        self.assertTrue(set_cookie_headers, "Expected a Set-Cookie header for new session.")

        # The session should be stored in self.server.sessions
        cookie_value = set_cookie_headers[0][1]
        session_id = cookie_value.split("=")[1].split(";")[0]
        self.assertIn(session_id, self.server.sessions)

    def test_session_usage(self):
        """
        Test that an existing session is reused if a valid session_id is provided.
        """
        # Create a session manually
        session_id = str(uuid.uuid4())
        self.server.sessions[session_id] = {"last_access": time.time()}

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
            "HTTP_COOKIE": f"session_id={session_id}",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        _ = b"".join(response).decode()

        # We should not receive a new Set-Cookie; we should reuse existing one.
        set_cookie_headers = [h for h in self._wsgi_headers if h[0] == 'Set-Cookie']
        self.assertFalse(set_cookie_headers, "Did not expect a new Set-Cookie header.")

        # Ensure we didn't lose the session
        self.assertIn(session_id, self.server.sessions, "Existing session should still be present.")

    @unittest.skip("Requires a valid 'greet.html' in the 'templates' folder to work.")
    def test_template_rendering(self):
        """
        Optional test for verifying a Jinja2 template render. This test will
        require a 'templates/greet.html' file that references a variable 'name'.

        Example 'greet.html' content:

            <h1>Hello {{ name }}!</h1>
        """
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/greet_template",
            "QUERY_STRING": "name=Tester",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        response = self.server.wsgi_app(environ, self._start_response)
        body = b"".join(response).decode()

        self.assertEqual(self._wsgi_status, "200 OK")
        self.assertIn("<h1>Hello Tester!</h1>", body)


if __name__ == '__main__':
    unittest.main()

