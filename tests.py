import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs
from micropie import App, InMemorySessionBackend, Request, WebSocketRequest, SESSION_TIMEOUT, ConnectionClosed, HttpMiddleware

class MicroPieTestCase(unittest.IsolatedAsyncioTestCase):
    """Base test case for MicroPie tests with common setup."""
    
    async def asyncSetUp(self):
        """Initialize the App instance for each test."""
        self.app = App(session_backend=InMemorySessionBackend())

    def create_mock_scope(self, path="/index", method="GET", headers=None, query_string=b"", scope_type="http"):
        """Create a mock ASGI scope for testing."""
        if headers is None:
            headers = []
        return {
            "type": scope_type,
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": query_string
        }

class TestRequest(MicroPieTestCase):
    """Tests for the Request and WebSocketRequest classes."""

    async def test_request_initialization(self):
        """Verify that the Request object initializes correctly with scope data."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"host", b"example.com"), (b"cookie", b"session_id=123")],
            "query_string": b"param1=value1"
        }
        request = Request(scope)
        request.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
        self.assertEqual(request.method, "GET", "Request method should be GET")
        self.assertEqual(request.headers["host"], "example.com", "Host header should be set")
        self.assertEqual(request.query_params, {"param1": ["value1"]}, "Query params should be parsed")
        self.assertEqual(request.session, {}, "Session should be empty initially")

    async def test_websocket_request_initialization(self):
        """Verify that WebSocketRequest initializes correctly."""
        scope = {
            "type": "websocket",
            "path": "/ws_test",
            "headers": [(b"host", b"example.com")],
            "query_string": b"param1=value1"
        }
        request = WebSocketRequest(scope)
        request.query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
        self.assertEqual(request.scope["path"], "/ws_test", "WebSocketRequest path should be set")
        self.assertEqual(request.query_params, {"param1": ["value1"]}, "Query params should be parsed")

class TestSession(MicroPieTestCase):
    """Tests for session management and cookie parsing."""

    async def test_in_memory_session_backend(self):
        """Test InMemorySessionBackend load and save operations."""
        backend = InMemorySessionBackend()
        session_id = str(uuid.uuid4())
        session_data = {"user_id": "123", "name": "Test User"}

        await backend.save(session_id, session_data, SESSION_TIMEOUT)
        loaded_data = await backend.load(session_id)
        self.assertEqual(loaded_data, session_data, "Loaded session data should match saved data")

        backend.last_access[session_id] = 0  # Simulate expired session
        expired_data = await backend.load(session_id)
        self.assertEqual(expired_data, {}, "Expired session should return empty dict")

    async def test_cookie_parsing(self):
        """Test parsing of cookie header."""
        cookie_header = "session_id=abc123; theme=dark; user=john"
        cookies = self.app._parse_cookies(cookie_header)
        self.assertEqual(cookies, {
            "session_id": "abc123",
            "theme": "dark",
            "user": "john"
        }, "Cookies should be parsed correctly")
        self.assertEqual(self.app._parse_cookies(""), {}, "Empty cookie header should return empty dict")

    async def test_session_management(self):
        """Test session handling in request processing."""
        async def set_session(self):
            self.request.session["user"] = "test_user"
            return 200, "Session set"

        setattr(self.app, "set_session", set_session.__get__(self.app, App))

        scope = self.create_mock_scope(path="/set_session")
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        set_cookie_call = None
        for call in send.call_args_list:
            args = call[0][0]
            if args["type"] == "http.response.start" and any(h[0] == b"Set-Cookie" for h in args["headers"]):
                set_cookie_call = args
                break
        self.assertIsNotNone(set_cookie_call, "Set-Cookie header not found")
        self.assertTrue(
            any(h[0] == b"Set-Cookie" and b"session_id=" in h[1] for h in set_cookie_call["headers"]),
            "Set-Cookie header with session_id not found"
        )
        self.assertEqual(set_cookie_call["status"], 200, "Status should be 200")

class TestRouting(MicroPieTestCase):
    """Tests for HTTP and WebSocket routing."""

    async def test_app_handler(self):
        """Test handling of a simple HTTP request with query parameter."""
        async def index(self, name="World"):
            return 200, f"Hello, {name}!"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index", query_string=b"name=Test")
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

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

    async def test_404_response(self):
        """Test 404 response for non-existent route."""
        scope = self.create_mock_scope(path="/nonexistent")
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

    async def test_missing_parameter(self):
        """Test handler with missing required parameter."""
        async def index(self, required_param):
            return "Should not reach here"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
        })
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"400 Bad Request: Missing required parameter 'required_param'",
            "more_body": False
        })

class TestWebSocket(MicroPieTestCase):
    """Tests for WebSocket handling."""

    async def test_websocket_handler(self):
        """Test WebSocket connection and message handling."""
        async def ws_echo(self, ws):
            await ws.accept()
            msg = await ws.receive_text()
            await ws.send_text(f"Echo: {msg}")
            await ws.close(1000, "Done")

        setattr(self.app, "ws_echo", ws_echo.__get__(self.app, App))

        scope = self.create_mock_scope(path="/echo", scope_type="websocket")
        receive = AsyncMock(side_effect=[
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "Hello"},
            {"type": "websocket.disconnect", "code": 1000}
        ])
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "websocket.accept",
            "subprotocol": None,
            "headers": []
        })
        send.assert_any_call({
            "type": "websocket.send",
            "text": "Echo: Hello"
        })
        send.assert_any_call({
            "type": "websocket.close",
            "code": 1000,
            "reason": "Done"
        })

    async def test_websocket_missing_handler(self):
        """Test WebSocket 1008 response for non-existent route."""
        scope = self.create_mock_scope(path="/nonexistent", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "websocket.close",
            "code": 1008,
            "reason": "No matching WebSocket route"
        })

class TestMiddleware(MicroPieTestCase):
    """Tests for HTTP and WebSocket middleware."""

    async def test_http_middleware(self):
        """Test HTTP middleware before and after request."""
        class TestMiddleware(HttpMiddleware):
            async def before_request(self, request):
                request.custom_data = "set_by_middleware"
                return None
            async def after_request(self, request, status_code, response_body, extra_headers):
                return {"status_code": 201, "body": f"{response_body} + middleware", "headers": extra_headers}

        self.app.middlewares.append(TestMiddleware())

        async def index(self):
            return f"Data: {self.request.custom_data}"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "http.response.start",
            "status": 201,
            "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
        })
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"Data: set_by_middleware + middleware",
            "more_body": False
        })

class TestResponseHandling(MicroPieTestCase):
    """Tests for response handling and edge cases."""

    async def test_json_handling(self):
        """Test JSON request and response handling."""
        async def json_handler(self):
            return self.request.get_json

        setattr(self.app, "json_handler", json_handler.__get__(self.app, App))

        scope = self.create_mock_scope(
            path="/json_handler",
            method="POST",
            headers=[(b"content-type", b"application/json")]
        )
        receive = AsyncMock(return_value={"type": "http.request", "body": b'{"key": "value"}', "more_body": False})
        send = AsyncMock()

        with patch("micropie.json") as mock_json:
            mock_json.loads.return_value = {"key": "value"}
            mock_json.dumps.return_value = b'{"key": "value"}'

            await self.app(scope, receive, send)

            mock_json.loads.assert_called_once()
            mock_json.dumps.assert_called_once()
            send.assert_any_call({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"Content-Type", b"application/json")]
            })
            send.assert_any_call({
                "type": "http.response.body",
                "body": b'{"key": "value"}',
                "more_body": False
            })

    async def test_invalid_json(self):
        """Test handling of invalid JSON in POST request."""
        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[(b"content-type", b"application/json")]
        )
        receive = AsyncMock(return_value={"type": "http.request", "body": b"{invalid}", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
        })
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"400 Bad Request: Bad JSON",
            "more_body": False
        })

    async def test_header_injection(self):
        """Test protection against header injection."""
        async def index(self):
            return 200, "Test", [("Bad-Header", "value\r\nInject: malicious")]

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()

        await self.app(scope, receive, send)

        start_call = None
        for call in send.call_args_list:
            args = call[0][0]
            if args["type"] == "http.response.start":
                start_call = args
                break
        self.assertIsNotNone(start_call, "Response start call not found")
        self.assertEqual(start_call["status"], 200, "Status should be 200")
        self.assertEqual(
            start_call["headers"],
            [(b"Content-Type", b"text/html; charset=utf-8")],
            "Malicious header should be filtered out"
        )
        send.assert_any_call({
            "type": "http.response.body",
            "body": b"Test",
            "more_body": False
        })

    async def test_redirect(self):
        """Test redirect response generation."""
        location = "/new-page"
        extra_headers = [("X-Custom", "Value")]
        status_code, body, headers = self.app._redirect(location, extra_headers)
        self.assertEqual(status_code, 302, "Redirect should return 302 status")
        self.assertEqual(body, "", "Redirect body should be empty")
        self.assertIn(("Location", location), headers, "Location header should be set")
        self.assertIn(("X-Custom", "Value"), headers, "Extra headers should be included")

class TestOptionalDependencies(MicroPieTestCase):
    """Tests for behavior with missing optional dependencies."""

    async def test_no_multipart_installed(self):
        """Test behavior when multipart is not installed."""
        with patch("micropie.MULTIPART_INSTALLED", False):
            scope = self.create_mock_scope(
                path="/index",
                method="POST",
                headers=[(b"content-type", b"multipart/form-data; boundary=----boundary")]
            )
            receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
            send = AsyncMock()

            await self.app(scope, receive, send)

            send.assert_any_call({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
            })
            send.assert_any_call({
                "type": "http.response.body",
                "body": b"500 Internal Server Error",
                "more_body": False
            })

    async def test_no_jinja_installed(self):
        """Test behavior when Jinja2 is not installed."""
        with patch("micropie.JINJA_INSTALLED", False):
            async def index(self):
                return await self._render_template("test.html")
            setattr(self.app, "index", index.__get__(self.app, App))

            scope = self.create_mock_scope(path="/index")
            receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
            send = AsyncMock()

            await self.app(scope, receive, send)

            send.assert_any_call({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")]
            })
            send.assert_any_call({
                "type": "http.response.body",
                "body": b"500 Internal Server Error: Jinja2 not installed.",
                "more_body": False
            })

if __name__ == "__main__":
    unittest.main()
