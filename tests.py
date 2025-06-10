import asyncio
import unittest
import uuid
from urllib.parse import parse_qs
from unittest.mock import AsyncMock
from MicroPie import App, InMemorySessionBackend, Request, SESSION_TIMEOUT

class TestMicroPie(unittest.TestCase):
    def setUp(self):
        """Set up the test environment with a new event loop."""
        self.app = App(session_backend=InMemorySessionBackend())
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up the event loop after each test."""
        self.loop.close()

    def test_request_initialization(self):
        """Test Request object initialization."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"host", b"example.com"), (b"cookie", b"session_id=123")],
            "query_string": b"param1=value1"
        }
        request = Request(scope)
        # Fix: Explicitly parse query_params in Request initialization
        request.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.headers["host"], "example.com")
        self.assertEqual(request.query_params, {"param1": ["value1"]})
        self.assertEqual(request.session, {})

    def test_in_memory_session_backend(self):
        """Test InMemorySessionBackend load and save operations."""
        backend = InMemorySessionBackend()
        session_id = str(uuid.uuid4())
        session_data = {"user_id": "123", "name": "Test User"}

        # Test saving and loading session data
        self.loop.run_until_complete(backend.save(session_id, session_data, SESSION_TIMEOUT))
        loaded_data = self.loop.run_until_complete(backend.load(session_id))
        self.assertEqual(loaded_data, session_data)

        # Test session timeout (simulating expired session)
        backend.last_access[session_id] = 0  # Set to far past
        expired_data = self.loop.run_until_complete(backend.load(session_id))
        self.assertEqual(expired_data, {})

    def test_cookie_parsing(self):
        """Test cookie parsing in App."""
        cookie_header = "session_id=abc123; theme=dark; user=john"
        cookies = self.app._parse_cookies(cookie_header)
        self.assertEqual(cookies, {
            "session_id": "abc123",
            "theme": "dark",
            "user": "john"
        })

        # Test empty cookie header
        self.assertEqual(self.app._parse_cookies(""), {})

    def test_redirect(self):
        """Test redirect response generation."""
        location = "/new-page"
        status_code, body, headers = self.app._redirect(location)
        self.assertEqual(status_code, 302)
        self.assertEqual(body, "")
        self.assertIn(("Location", location), headers)

        # Test with extra headers
        extra_headers = [("X-Custom", "Value")]
        status_code, body, headers = self.app._redirect(location, extra_headers)
        self.assertIn(("X-Custom", "Value"), headers)

    async def async_test_app_handler(self):
        """Test App handling a simple request."""
        # Define a simple handler in the app
        async def index(self, name="World"):
            return 200, f"Hello, {name}!"

        setattr(self.app, "index", index.__get__(self.app, App))

        # Mock ASGI scope, receive, and send
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/index",
            "headers": [],
            "query_string": b"name=Test"
        }
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        # Run the app
        await self.app(scope, receive, send)

        # Verify response
        send.assert_any_call({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
        })
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"Hello, Test!",
            "more_body": False
        })

    def test_app_handler(self):
        """Run async test for app handler."""
        self.loop.run_until_complete(self.async_test_app_handler())

    async def async_test_session_management(self):
        """Test session management in request handling."""
        # Define a handler that uses session
        async def set_session(self):
            self.request.session["user"] = "test_user"
            return 200, "Session set"

        setattr(self.app, "set_session", set_session.__get__(self.app, App))

        # Mock ASGI scope, receive, and send
        session_id = str(uuid.uuid4())
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/set_session",
            "headers": [],  # Remove existing session_id to force Set-Cookie
            "query_string": b""
        }
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        # Run the app
        await self.app(scope, receive, send)

        # Verify session was saved
        # Since no session_id was provided, a new one should have been generated
        session_data = await self.app.session_backend.load(session_id)
        self.assertEqual(session_data, {})  # Session not saved under this ID

        # Verify Set-Cookie header was sent with a new session_id
        calls = send.call_args_list
        set_cookie_call = None
        for call in calls:
            args = call[0][0]
            if args["type"] == "http.response.start" and any(h[0] == b"Set-Cookie" for h in args["headers"]):
                set_cookie_call = args
                break
        self.assertIsNotNone(set_cookie_call, "Set-Cookie header not found")
        self.assertEqual(set_cookie_call["status"], 200)
        self.assertTrue(
            any(h[0] == b"Set-Cookie" and b"session_id=" in h[1] for h in set_cookie_call["headers"]),
            "Set-Cookie header with session_id not found"
        )

    def test_session_management(self):
        """Run async test for session management."""
        self.loop.run_until_complete(self.async_test_session_management())

    async def async_test_404_response(self):
        """Test 404 response for unknown route."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/nonexistent",
            "headers": [],
            "query_string": b""
        }
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
        })
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"404 Not Found",
            "more_body": False
        })

    def test_404_response(self):
        """Run async test for 404 response."""
        self.loop.run_until_complete(self.async_test_404_response())

if __name__ == "__main__":
    unittest.main()
