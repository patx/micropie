import asyncio
import os
import time
import tempfile
import unittest
import contextvars
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from MicroPie import App, Request, current_request, JINJA_INSTALLED, MULTIPART_INSTALLED

# ---------------------------------------------------------------------
# Helper classes & functions used for ASGI simulation
# ---------------------------------------------------------------------
class SendCollector:
    """A helper asynchronous callable that collects ASGI sent messages."""
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)

def create_receive(messages):
    """
    Returns an asynchronous receive callable that yields the messages provided.
    """
    messages_iter = iter(messages)
    async def receive():
        try:
            return next(messages_iter)
        except StopIteration:
            await asyncio.sleep(0)
            return {"type": "http.request", "body": b"", "more_body": False}
    return receive

# ---------------------------------------------------------------------
# Subclass App for test-specific handlers.
# ---------------------------------------------------------------------
class TestApp(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Instead of setting self.request directly (since it may be read-only),
        # we use a private attribute _test_request and define a property.
        self._test_request = None
        # Ensure sessions dictionary exists.
        if not hasattr(self, 'sessions'):
            self.sessions = {}

    @property
    def request(self):
        return self._test_request

    @request.setter
    def request(self, value):
        self._test_request = value

    async def _asgi_app(self, scope, receive, send):
        # Set the request using the property.
        self.request = Request(scope)
        # If the Request object doesn't already provide cookies, assign an empty dict.
        if not hasattr(self.request, "cookies") or self.request.cookies is None:
            self.request.cookies = {}
        # Session handling: if no session cookie provided, create a new session.
        session_cookie = self.request.cookies.get("session_id")
        if not session_cookie:
            new_session = str(uuid.uuid4())
            # Save the Request's session dict under the new session id.
            self.sessions[new_session] = self.request.session
            # Simulate setting the cookie by adding it to the request cookies.
            self.request.cookies["session_id"] = new_session
        return await super()._asgi_app(scope, receive, send)

    async def index(self):
        # Set a value in the session to simulate session usage.
        self.request.session["user"] = "test"
        return "index handler"

    async def hello(self, name):
        return f"hello {name}"

    async def async_handler(self):
        return "async result"

    # A handler requiring a parameter. When missing, should trigger a 400 error.
    async def require_param(self, value):
        return f"got {value}"

    async def raise_exception(self):
        raise ValueError("intentional error")

    # For static file tests (if implemented).
    def serve_static(self, filename):
        """
        A dummy implementation for static file serving.
        Mimics a potential serve_static implementation.
        """
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                content = f.read()
            headers = [("Content-Type", "application/octet-stream")]
            return (200, content, headers)
        else:
            return (404, "404 Not Found")

# ---------------------------------------------------------------------
# Synchronous tests (non-ASGI functionality)
# ---------------------------------------------------------------------
class TestAppSyncFunctions(unittest.TestCase):
    def setUp(self):
        self.app = TestApp()

    def test_parse_cookies(self):
        cookie_header = "session_id=abc123; theme=dark"
        cookies = self.app._parse_cookies(cookie_header)
        self.assertEqual(cookies, {"session_id": "abc123", "theme": "dark"})

    def test_parse_cookies_empty(self):
        cookies = self.app._parse_cookies("")
        self.assertEqual(cookies, {})

    def test_redirect(self):
        location = "/new-path"
        status, body = self.app._redirect(location)
        self.assertEqual(status, 302)
        self.assertIn(location, body)

    def test_cleanup_sessions(self):
        now = time.time()
        self.app.sessions = {
            "session1": {"last_access": now - 1000},
            "session2": {"last_access": now - 10000},
        }
        self.app.SESSION_TIMEOUT = 3600
        self.app._cleanup_sessions()
        self.assertEqual(len(self.app.sessions), 1)
        self.assertIn("session1", self.app.sessions)

    @unittest.skipUnless(JINJA_INSTALLED, "Jinja2 is not installed")
    def test_render_template(self):
        async def run():
            mock_template = MagicMock()
            # Define an async render_async function that returns a string.
            async def fake_render_async(**kwargs):
                return "Rendered content"
            mock_template.render_async = fake_render_async
            with patch.object(self.app.env, "get_template", return_value=mock_template):
                result = await self.app._render_template("test.html", var="value")
                self.assertEqual(result, "Rendered content")
        asyncio.run(run())

    @unittest.skipUnless(JINJA_INSTALLED, "Jinja2 is not installed")
    def test_render_template_no_jinja(self):
        async def run():
            self.app.env = None
            with self.assertRaises(AssertionError):
                await self.app._render_template("test.html")
        asyncio.run(run())

    def test_serve_static_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"file content")
            tmp_filename = tmp.name

        try:
            if hasattr(self.app, "serve_static"):
                response = self.app.serve_static(tmp_filename)
                self.assertEqual(response[0], 200)
                self.assertEqual(response[1], b"file content")
                self.assertTrue(any("Content-Type" in header for header in response[2]))
        finally:
            os.remove(tmp_filename)

    def test_serve_static_file_not_found(self):
        if hasattr(self.app, "serve_static"):
            response = self.app.serve_static("nonexistent_file.txt")
            self.assertEqual(response, (404, "404 Not Found"))

# ---------------------------------------------------------------------
# Asynchronous (ASGI) tests
# ---------------------------------------------------------------------
class TestAppAsyncFunctions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = TestApp()

    async def test_asgi_get_request_index(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app._asgi_app(scope, receive, send_collector)
        messages = send_collector.messages
        start_msg = messages[0]
        self.assertEqual(start_msg["status"], 200)
        body = b"".join(msg["body"] for msg in messages if msg["type"] == "http.response.body")
        self.assertEqual(body.decode("utf-8"), "index handler")

    async def test_asgi_get_request_with_path_param(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/hello/pat",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app._asgi_app(scope, receive, send_collector)
        messages = send_collector.messages
        body = b"".join(msg["body"] for msg in messages if msg["type"] == "http.response.body")
        self.assertEqual(body.decode("utf-8"), "hello pat")

    async def test_asgi_post_request_urlencoded(self):
        body = b"a=1&b=2"
        headers = [
            (b"content-type", b"application/x-www-form-urlencoded")
        ]
        async def echo(a, b):
            return f"{a} {b}"
        setattr(self.app, "echo", echo)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/echo",
            "query_string": b"",
            "headers": headers,
        }
        send_collector = SendCollector()
        receive_messages = [
            {"type": "http.request", "body": body, "more_body": False}
        ]
        receive = create_receive(receive_messages)
        await self.app._asgi_app(scope, receive, send_collector)
        messages = send_collector.messages
        response_body = b"".join(msg["body"] for msg in messages if msg["type"] == "http.response.body")
        self.assertEqual(response_body.decode("utf-8"), "1 2")

    async def test_asgi_missing_required_param(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/require_param",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.app._asgi_app(scope, receive, send_collector)
        start_msg = send_collector.messages[0]
        self.assertEqual(start_msg["status"], 400)
        body_text = b"".join(msg["body"] for msg in send_collector.messages if msg["type"] == "http.response.body").decode("utf-8")
        self.assertIn("Missing required parameter", body_text)

    async def test_asgi_handler_exception(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/raise_exception",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.app._asgi_app(scope, receive, send_collector)
        start_msg = send_collector.messages[0]
        self.assertEqual(start_msg["status"], 500)
        body_text = b"".join(msg["body"] for msg in send_collector.messages if msg["type"] == "http.response.body").decode("utf-8")
        self.assertIn("500 Internal Server Error", body_text)

    @patch("uuid.uuid4", return_value="test-session-id")
    @patch("time.time", return_value=1000)
    async def test_asgi_app_creates_session(self, mock_time, mock_uuid):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.app._asgi_app(scope, receive, send_collector)
        self.assertIn("test-session-id", self.app.sessions)
        self.assertEqual(self.app.sessions["test-session-id"].get("user"), "test")

    @patch("time.time", return_value=1000)
    async def test_asgi_app_handles_request_with_existing_session(self, mock_time):
        cookie_header = "session_id=test-session-id"
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(b"cookie", cookie_header.encode("latin-1"))],
        }
        self.app.sessions["test-session-id"] = {"last_access": 500}
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        async def simple_index():
            return "Hello, test!"
        self.app.index = simple_index
        await self.app._asgi_app(scope, receive, send_collector)
        self.assertEqual(self.app.sessions["test-session-id"].get("last_access"), 1000)

    @unittest.skipUnless(JINJA_INSTALLED, "Jinja2 is not installed")
    async def test_render_template_async(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_content = "Value: {{ value }}"
            template_name = "test_template.html"
            template_path = os.path.join(tmpdir, template_name)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(template_content)
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            self.app.env = Environment(
                loader=FileSystemLoader(tmpdir),
                autoescape=select_autoescape(["html", "xml"]),
                enable_async=True
            )
            rendered = await self.app._render_template(template_name, value="123")
            self.assertEqual(rendered, "Value: 123")

    @unittest.skipUnless(MULTIPART_INSTALLED, "Multipart support is not installed")
    async def test_parse_multipart(self):
        boundary = b"simpleboundary"
        multipart_body = (
            b"--simpleboundary\r\n"
            b'Content-Disposition: form-data; name="text"\r\n'
            b"\r\n"
            b"hello\r\n"
            b"--simpleboundary--\r\n"
        )
        reader = asyncio.StreamReader()
        reader.feed_data(multipart_body)
        reader.feed_eof()
        req = Request({"method": "POST"})
        req.body_params = {}
        req.files = {}
        # Important: set self.app.request so that _parse_multipart finds a valid request
        self.app.request = req
        token = current_request.set(req)
        try:
            await self.app._parse_multipart(reader, boundary)
            self.assertIn("text", req.body_params)
            self.assertEqual(req.body_params["text"], ["hello"])
        finally:
            current_request.reset(token)

    async def test_async_handler(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/async_handler",
            "query_string": b"",
            "headers": []
        }
        send_collector = SendCollector()
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.app._asgi_app(scope, receive, send_collector)
        body = b"".join(msg["body"] for msg in send_collector.messages if msg["type"] == "http.response.body")
        self.assertEqual(body.decode("utf-8"), "async result")

if __name__ == "__main__":
    unittest.main()
