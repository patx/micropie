import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from MicroPie import Server
import os
import uuid

class TestServer(unittest.TestCase):
    def setUp(self):
        self.server = Server()

    def test_parse_cookies(self):
        cookie_header = "session_id=abc123; theme=dark"
        cookies = self.server._parse_cookies(cookie_header)
        self.assertEqual(cookies, {"session_id": "abc123", "theme": "dark"})

    def test_parse_cookies_empty(self):
        cookies = self.server._parse_cookies("")
        self.assertEqual(cookies, {})

    def test_redirect(self):
        location = "/new-path"
        status, body = self.server.redirect(location)
        self.assertEqual(status, 302)
        self.assertIn(location, body)

    @patch("os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=MagicMock)
    def test_serve_static_file(self, mock_open, mock_isfile):
        mock_open.return_value.__enter__.return_value.read.return_value = b"file content"
        response = self.server.serve_static("test.txt")
        self.assertEqual(response[0], 200)
        self.assertEqual(response[1], b"file content")
        self.assertEqual(response[2][0][0], "Content-Type")

    @patch("os.path.isfile", return_value=False)
    def test_serve_static_file_not_found(self, mock_isfile):
        response = self.server.serve_static("missing.txt")
        self.assertEqual(response, (404, "404 Not Found"))

    def test_cleanup_sessions(self):
        self.server.sessions = {
            "session1": {"last_access": time.time() - 1000},
            "session2": {"last_access": time.time() - 10000},
        }
        self.server.SESSION_TIMEOUT = 3600
        self.server.cleanup_sessions()
        self.assertEqual(len(self.server.sessions), 1)
        self.assertIn("session1", self.server.sessions)

    @patch("uuid.uuid4", return_value="test-session-id")
    @patch("time.time", return_value=1000)
    async def test_asgi_app_creates_session(self, mock_time, mock_uuid):
        mock_send = AsyncMock()
        mock_receive = AsyncMock(return_value={"type": "http.request", "body": b""})

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        }

        async def mock_index():
            return "Hello, world!"

        self.server.index = mock_index

        await self.server.asgi_app(scope, mock_receive, mock_send)

        self.assertIn("test-session-id", self.server.sessions)
        self.assertEqual(self.server.sessions["test-session-id"].get("last_access"), 1000)

    @patch("time.time", return_value=1000)
    async def test_asgi_app_handles_request(self, mock_time):
        mock_send = AsyncMock()
        mock_receive = AsyncMock(return_value={"type": "http.request", "body": b""})

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", b"session_id=test-session-id")],
        }

        self.server.sessions["test-session-id"] = {"last_access": 500}

        async def mock_index():
            return "Hello, test!"

        self.server.index = mock_index

        await self.server.asgi_app(scope, mock_receive, mock_send)

        self.assertEqual(self.server.sessions["test-session-id"].get("last_access"), 1000)

    @patch("jinja2.Environment.get_template")
    def test_render_template(self, mock_get_template):
        mock_template = MagicMock()
        mock_template.render.return_value = "Rendered content"
        mock_get_template.return_value = mock_template

        result = self.server.render_template("test.html", var="value")
        self.assertEqual(result, "Rendered content")
        mock_template.render.assert_called_with({"var": "value"})

    def test_render_template_no_jinja(self):
        self.server.env = None
        with self.assertRaises(ImportError):
            self.server.render_template("test.html")

if __name__ == "__main__":
    unittest.main()

