import asyncio
import functools
import json as std_json
import threading
import unittest
import uuid
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs
from micropie import (
    App,
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_FORM_FIELD_SIZE,
    InMemorySessionBackend,
    MULTIPART_INSTALLED,
    Request,
    WebSocketRequest,
    SESSION_TIMEOUT,
    ConnectionClosed,
    HttpMiddleware,
    MultipartFileError,
)


VALID_SESSION_ID = "00000000-0000-4000-8000-000000000001"
ATTACKER_SESSION_ID = "00000000-0000-4000-8000-000000000002"


class CountingSessionBackend(InMemorySessionBackend):
    def __init__(self):
        super().__init__()
        self.load_calls = []
        self.save_calls = []

    async def load(self, session_id):
        self.load_calls.append(session_id)
        return await super().load(session_id)

    async def save(self, session_id, data, timeout):
        self.save_calls.append((session_id, dict(data), timeout))
        await super().save(session_id, data, timeout)


class MicroPieTestCase(unittest.IsolatedAsyncioTestCase):
    """Base test case for MicroPie tests with common setup."""

    async def asyncSetUp(self):
        """Initialize the App instance for each test."""
        self.app = App(session_backend=InMemorySessionBackend())

    def create_mock_scope(
        self,
        path="/index",
        method="GET",
        headers=None,
        query_string=b"",
        scope_type="http",
    ):
        """Create a mock ASGI scope for testing."""
        if headers is None:
            headers = []
        return {
            "type": scope_type,
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": query_string,
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
            "query_string": b"param1=value1",
        }
        request = Request(scope)
        request.query_params = parse_qs(
            scope.get("query_string", b"").decode("utf-8", "ignore")
        )
        self.assertEqual(request.method, "GET", "Request method should be GET")
        self.assertEqual(
            request.headers["host"], "example.com", "Host header should be set"
        )
        self.assertEqual(
            request.query_params,
            {"param1": ["value1"]},
            "Query params should be parsed",
        )
        self.assertEqual(request.session, {}, "Session should be empty initially")

    async def test_websocket_request_initialization(self):
        """Verify that WebSocketRequest initializes correctly."""
        scope = {
            "type": "websocket",
            "path": "/ws_test",
            "headers": [(b"host", b"example.com")],
            "query_string": b"param1=value1",
        }
        request = WebSocketRequest(scope)
        request.query_params = parse_qs(
            scope.get("query_string", b"").decode("utf-8", "ignore")
        )
        self.assertEqual(
            request.scope["path"], "/ws_test", "WebSocketRequest path should be set"
        )
        self.assertEqual(
            request.query_params,
            {"param1": ["value1"]},
            "Query params should be parsed",
        )

    async def test_request_query_and_form_helpers(self):
        """Verify helper accessors return first values and defaults."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [],
            "query_string": b"name=Alice&name=Bob",
            "body_params": {"username": ["test-user"]},
        }
        request = Request(scope)
        request.query_params = parse_qs(
            scope.get("query_string", b"").decode("utf-8", "ignore")
        )

        self.assertEqual(request.query("name"), "Alice")
        self.assertIsNone(request.query("missing"))
        self.assertEqual(request.query("missing", "fallback"), "fallback")

        self.assertEqual(request.form("username"), "test-user")
        self.assertIsNone(request.form("missing"))
        self.assertEqual(request.form("missing", "fallback"), "fallback")

    async def test_request_json_helper(self):
        """Verify JSON helper returns payloads, keys, and defaults."""
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/json",
                "headers": [],
                "json_body": {"username": "alice", "age": 42},
            }
        )
        self.assertFalse(hasattr(request, "get_json"))
        self.assertEqual(request.json(), {"username": "alice", "age": 42})
        self.assertEqual(request.json("username"), "alice")
        self.assertIsNone(request.json("missing"))
        self.assertEqual(request.json("missing", "fallback"), "fallback")

        list_payload_request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/json",
                "headers": [],
                "json_body": ["a", "b"],
            }
        )
        self.assertEqual(list_payload_request.json(), ["a", "b"])
        self.assertEqual(list_payload_request.json("username", "fallback"), "fallback")


class TestSession(MicroPieTestCase):
    """Tests for session management and cookie parsing."""

    async def test_in_memory_session_backend(self):
        """Test InMemorySessionBackend load and save operations."""
        backend = InMemorySessionBackend()
        session_id = str(uuid.uuid4())
        session_data = {"user_id": "123", "name": "Test User"}

        await backend.save(session_id, session_data, SESSION_TIMEOUT)
        loaded_data = await backend.load(session_id)
        self.assertEqual(
            loaded_data, session_data, "Loaded session data should match saved data"
        )

        backend.last_access[session_id] = 0  # Simulate expired session
        expired_data = await backend.load(session_id)
        self.assertEqual(expired_data, {}, "Expired session should return empty dict")

    async def test_in_memory_backend_honors_each_saved_timeout(self):
        """Each in-memory session should use the timeout supplied to save()."""
        backend = InMemorySessionBackend()

        with patch("micropie.time.time", return_value=100.0):
            await backend.save("short", {"user": "alice"}, 10)
            await backend.save("long", {"user": "bob"}, 100)

        backend._cleanup(now=111.0, force=True)
        self.assertNotIn("short", backend.sessions)
        self.assertNotIn("short", backend.timeouts)
        self.assertIn("long", backend.sessions)

        with patch("micropie.time.time", return_value=150.0):
            self.assertEqual(await backend.load("long"), {"user": "bob"})
        with patch("micropie.time.time", return_value=250.0):
            self.assertEqual(await backend.load("long"), {})

        self.assertNotIn("long", backend.sessions)
        self.assertNotIn("long", backend.timeouts)

    async def test_nonpositive_timeout_deletes_in_memory_session(self):
        """A non-positive timeout should delete even non-empty session data."""
        backend = InMemorySessionBackend()
        await backend.save("abc", {"user": "alice"}, 10)
        await backend.save("abc", {"user": "alice"}, 0)

        self.assertEqual(await backend.load("abc"), {})
        self.assertNotIn("abc", backend.timeouts)

    async def test_cookie_parsing(self):
        """Test parsing of cookie header."""
        cookie_header = "session_id=abc123; theme=dark; user=john"
        cookies = self.app._parse_cookies(cookie_header)
        self.assertEqual(
            cookies,
            {"session_id": "abc123", "theme": "dark", "user": "john"},
            "Cookies should be parsed correctly",
        )
        self.assertEqual(
            self.app._parse_cookies(""),
            {},
            "Empty cookie header should return empty dict",
        )

    async def test_session_management(self):
        """Test session handling in request processing."""

        async def set_session(self):
            self.request.session["user"] = "test_user"
            return 200, "Session set"

        setattr(self.app, "set_session", set_session.__get__(self.app, App))

        scope = self.create_mock_scope(path="/set_session")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        set_cookie_call = None
        for call in send.call_args_list:
            args = call[0][0]
            if args["type"] == "http.response.start" and any(
                h[0] == b"Set-Cookie" for h in args["headers"]
            ):
                set_cookie_call = args
                break
        self.assertIsNotNone(set_cookie_call, "Set-Cookie header not found")
        self.assertTrue(
            any(
                h[0] == b"Set-Cookie" and b"session_id=" in h[1]
                for h in set_cookie_call["headers"]
            ),
            "Set-Cookie header with session_id not found",
        )
        self.assertTrue(
            any(
                h[0] == b"Set-Cookie" and b"; Secure;" in h[1]
                for h in set_cookie_call["headers"]
            ),
            "Session cookies should be Secure by default",
        )
        self.assertEqual(set_cookie_call["status"], 200, "Status should be 200")

    async def test_app_session_configuration_controls_save_and_cookie(self):
        """App session settings should reach the backend and cookie formatter."""
        backend = CountingSessionBackend()
        self.app = App(
            session_backend=backend,
            session_timeout=123,
            session_cookie_secure=False,
        )

        async def set_session(self):
            self.request.session["user"] = "alice"
            return "OK"

        setattr(self.app, "set_session", set_session.__get__(self.app, App))
        scope = self.create_mock_scope(path="/set_session")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.save_calls[-1][2], 123)
        start = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.start"
        )
        cookie = next(
            value for name, value in start["headers"] if name == b"Set-Cookie"
        )
        self.assertIn(b"HttpOnly", cookie)
        self.assertNotIn(b"Secure", cookie)

    async def test_empty_session_transition_rotates_client_supplied_id(self):
        """A login must never persist under an unknown ID chosen by the client."""
        backend = CountingSessionBackend()
        self.app = App(session_backend=backend)

        async def login(self):
            self.request.session["user_id"] = 42
            return "logged in"

        setattr(self.app, "login", login.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/login",
            headers=[
                (
                    b"cookie",
                    f"session_id={ATTACKER_SESSION_ID}".encode("ascii"),
                )
            ],
        )
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.load_calls, [ATTACKER_SESSION_ID])
        self.assertIn((ATTACKER_SESSION_ID, {}, 0), backend.save_calls)
        start = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.start"
        )
        cookie = next(
            value for name, value in start["headers"] if name == b"Set-Cookie"
        ).decode("ascii")
        new_session_id = cookie.split(";", 1)[0].split("=", 1)[1]
        self.assertNotEqual(new_session_id, ATTACKER_SESSION_ID)
        self.assertEqual(uuid.UUID(new_session_id).version, 4)
        self.assertNotIn(ATTACKER_SESSION_ID, backend.sessions)
        self.assertEqual(backend.sessions[new_session_id], {"user_id": 42})

    async def test_invalid_session_cookie_never_reaches_backend(self):
        """Malformed or oversized backend keys should be discarded before load()."""
        backend = CountingSessionBackend()
        self.app = App(session_backend=backend)

        async def login(self):
            self.request.session["user_id"] = 42
            return "logged in"

        setattr(self.app, "login", login.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/login",
            headers=[(b"cookie", b"session_id=../../tmp/attacker-session")],
        )
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.load_calls, [])
        self.assertTrue(backend.save_calls)
        saved_session_id = backend.save_calls[-1][0]
        self.assertEqual(uuid.UUID(saved_session_id).version, 4)
        self.assertNotEqual(saved_session_id, "../../tmp/attacker-session")

    async def test_explicit_session_regeneration_rotates_existing_session(self):
        """Apps can rotate a populated session during a privilege change."""
        backend = CountingSessionBackend()
        await backend.save(VALID_SESSION_ID, {"cart": "item"}, SESSION_TIMEOUT)
        backend.load_calls.clear()
        backend.save_calls.clear()
        self.app = App(session_backend=backend)

        async def reauthenticate(self):
            self.request.session["user_id"] = 42
            self.request.regenerate_session()
            return "reauthenticated"

        setattr(
            self.app,
            "reauthenticate",
            reauthenticate.__get__(self.app, App),
        )
        scope = self.create_mock_scope(
            path="/reauthenticate",
            headers=[
                (b"cookie", f"session_id={VALID_SESSION_ID}".encode("ascii"))
            ],
        )
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertIn((VALID_SESSION_ID, {}, 0), backend.save_calls)
        self.assertNotIn(VALID_SESSION_ID, backend.sessions)
        new_session_id = backend.save_calls[-1][0]
        self.assertNotEqual(new_session_id, VALID_SESSION_ID)
        self.assertEqual(
            backend.sessions[new_session_id], {"cart": "item", "user_id": 42}
        )
        start = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.start"
        )
        cookie = next(
            value for name, value in start["headers"] if name == b"Set-Cookie"
        )
        self.assertIn(f"session_id={new_session_id}".encode("ascii"), cookie)

    async def test_custom_session_id_policy_supports_non_uuid_backends(self):
        """Custom backends can opt into their own validated ID format."""
        backend = CountingSessionBackend()
        await backend.save("signed.existing", {"user": "alice"}, SESSION_TIMEOUT)
        backend.load_calls.clear()
        backend.save_calls.clear()
        self.app = App(
            session_backend=backend,
            session_id_factory=lambda: "signed.fresh",
            session_id_validator=lambda value: (
                value if value.startswith("signed.") else None
            ),
        )

        async def profile(self):
            return self.request.session["user"]

        setattr(self.app, "profile", profile.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/profile",
            headers=[(b"cookie", b"session_id=signed.existing")],
        )
        send = AsyncMock()

        await self.app(
            scope,
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            ),
            send,
        )

        self.assertEqual(backend.load_calls, ["signed.existing"])
        self.assertEqual(backend.save_calls[-1][0], "signed.existing")
        send.assert_any_call(
            {"type": "http.response.body", "body": b"alice", "more_body": False}
        )

    async def test_app_rejects_invalid_limit_configuration(self):
        """Enabled body limits and session timeouts must be positive."""
        with self.assertRaisesRegex(ValueError, "body_timeout"):
            App(body_timeout=0)
        with self.assertRaisesRegex(ValueError, "max_body_size"):
            App(max_body_size=0)
        with self.assertRaisesRegex(ValueError, "max_form_field_size"):
            App(max_form_field_size=0)
        with self.assertRaisesRegex(ValueError, "session_timeout"):
            App(session_timeout=0)
        with self.assertRaisesRegex(ValueError, "session_id_factory"):
            App(session_id_factory=None)
        with self.assertRaisesRegex(ValueError, "session_id_validator"):
            App(session_id_validator="not-callable")

        unbounded = App(
            body_timeout=None,
            max_body_size=None,
            max_form_field_size=None,
        )
        self.assertIsNone(unbounded.body_timeout)
        self.assertIsNone(unbounded.max_body_size)
        self.assertIsNone(unbounded.max_form_field_size)

        defaults = App()
        self.assertEqual(defaults.max_body_size, DEFAULT_MAX_BODY_SIZE)
        self.assertEqual(
            defaults.max_form_field_size, DEFAULT_MAX_FORM_FIELD_SIZE
        )


class TestFastPaths(MicroPieTestCase):
    """Tests for optimized dispatch/session paths."""

    async def test_request_without_cookie_skips_session_load(self):
        """No session cookie should avoid a backend load call."""
        backend = CountingSessionBackend()
        self.app = App(session_backend=backend)

        async def index(self):
            return "OK"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.load_calls, [])
        self.assertEqual(backend.save_calls, [])

    async def test_request_with_session_cookie_loads_and_persists(self):
        """A session cookie should still load and save the matching session."""
        backend = CountingSessionBackend()
        await backend.save(VALID_SESSION_ID, {"user": "alice"}, SESSION_TIMEOUT)
        backend.load_calls.clear()
        backend.save_calls.clear()
        self.app = App(session_backend=backend)

        async def index(self):
            self.request.session["seen"] = "1"
            return self.request.session["user"]

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(
            path="/index",
            headers=[
                (b"cookie", f"session_id={VALID_SESSION_ID}".encode("ascii"))
            ],
        )
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.load_calls, [VALID_SESSION_ID])
        self.assertEqual(backend.save_calls[-1][0], VALID_SESSION_ID)
        self.assertEqual(
            backend.sessions[VALID_SESSION_ID], {"user": "alice", "seen": "1"}
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"alice", "more_body": False}
        )

    async def test_cached_handler_metadata_tracks_replaced_handler(self):
        """Replacing a handler should not reuse stale cached metadata."""

        async def greet(self):
            return "first"

        setattr(self.app, "greet", greet.__get__(self.app, App))

        scope = self.create_mock_scope(path="/greet")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()
        await self.app(scope, receive, send)
        send.assert_any_call(
            {"type": "http.response.body", "body": b"first", "more_body": False}
        )

        async def greet(self, name):
            return f"second {name}"

        setattr(self.app, "greet", greet.__get__(self.app, App))

        scope = self.create_mock_scope(path="/greet/Alice")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()
        await self.app(scope, receive, send)
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"second Alice",
                "more_body": False,
            }
        )

    async def test_http_argument_binding_fast_path_matches_existing_sources(self):
        """Request inputs bind while trusted session state is read explicitly."""

        async def combine(self, path_value, query_value, body_value, suffix="ok"):
            return {
                "path": path_value,
                "query": query_value,
                "body": body_value,
                "user": self.request.session["user"],
                "suffix": suffix,
            }

        setattr(self.app, "combine", combine.__get__(self.app, App))

        scope = self.create_mock_scope(
            path="/combine/path-part",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
            query_string=b"query_value=query-part",
        )
        scope["session"] = {"user": "alice"}
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": b"body_value=body-part",
                "more_body": False,
            }
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        body_call = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.body"
        )
        self.assertEqual(
            std_json.loads(body_call["body"]),
            {
                "path": "path-part",
                "query": "query-part",
                "body": "body-part",
                "user": "alice",
                "suffix": "ok",
            },
        )

    async def test_session_values_do_not_bind_http_handler_parameters(self):
        """A required request argument must not fall through to session state."""

        async def transfer(self, amount, user_id):
            return f"{user_id}:{amount}"

        setattr(self.app, "transfer", transfer.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/transfer", query_string=b"amount=10"
        )
        scope["session"] = {"user_id": "trusted-user"}
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"400 Bad Request: Missing required parameter 'user_id'",
                "more_body": False,
            }
        )

    async def test_request_input_cannot_shadow_explicit_session_read(self):
        """Extra query fields cannot replace session values read by the handler."""

        async def transfer(self, amount):
            return f"{self.request.session['user_id']}:{amount}"

        setattr(self.app, "transfer", transfer.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/transfer", query_string=b"amount=10&user_id=attacker"
        )
        scope["session"] = {"user_id": "trusted-user"}
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"trusted-user:10",
                "more_body": False,
            }
        )

    async def test_websocket_argument_binding_uses_cached_metadata(self):
        """WebSocket path and query argument binding should be unchanged."""

        async def ws_chat(self, ws, room, user="guest"):
            await ws.accept()
            await ws.send_text(f"{room}:{user}")
            await ws.close()

        setattr(self.app, "ws_chat", ws_chat.__get__(self.app, App))

        scope = self.create_mock_scope(
            path="/chat/lobby", query_string=b"user=alice", scope_type="websocket"
        )
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({"type": "websocket.send", "text": "lobby:alice"})

    async def test_http_keyword_only_and_var_keyword_binding(self):
        """Keyword-only parameters and **kwargs should bind by name."""

        async def options(self, *, name="guest", **kwargs):
            return {"name": name, "extras": kwargs}

        setattr(self.app, "options", options.__get__(self.app, App))
        payload = {"tags": [], "enabled": True}
        scope = self.create_mock_scope(
            path="/options",
            method="POST",
            headers=[(b"content-type", b"application/json")],
            query_string=b"name=alice&debug=1",
        )
        send = AsyncMock()

        await self.app(
            scope,
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": std_json.dumps(payload).encode("utf-8"),
                    "more_body": False,
                }
            ),
            send,
        )

        body = next(
            call[0][0]["body"]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.body"
        )
        self.assertEqual(
            std_json.loads(body),
            {
                "name": "alice",
                "extras": {"debug": "1", "tags": [], "enabled": True},
            },
        )

    async def test_websocket_keyword_only_and_var_keyword_binding(self):
        """WebSocket keyword-only parameters and **kwargs use query values."""

        async def ws_options(self, connection, *, room="lobby", **kwargs):
            await connection.accept()
            await connection.send_text(f"{room}:{kwargs['debug']}")
            await connection.close()

        setattr(self.app, "ws_options", ws_options.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/options",
            query_string=b"room=staff&debug=1",
            scope_type="websocket",
        )
        send = AsyncMock()

        await self.app(
            scope,
            AsyncMock(return_value={"type": "websocket.connect"}),
            send,
        )

        send.assert_any_call({"type": "websocket.send", "text": "staff:1"})


class TestRequestInputParsing(MicroPieTestCase):
    """Tests for consistent tolerant URL-encoded parsing."""

    async def test_query_and_form_bodies_share_legacy_tolerant_parsing(self):
        """The same URL-encoded bytes should produce the same parsed mapping."""
        cases = (
            (b"value=", {}),
            (b"value", {}),
            (b"value=%ZZ", {"value": ["%ZZ"]}),
            (b"value=%FF", {"value": ["\ufffd"]}),
            (b"value=before\xffafter", {"value": ["beforeafter"]}),
        )

        parsed_bodies = []

        async def inspect_form(self):
            parsed_bodies.append(self.request.body_params)
            return "OK"

        setattr(
            self.app,
            "inspect_form",
            inspect_form.__get__(self.app, App),
        )

        for encoded, expected in cases:
            with self.subTest(encoded=encoded):
                self.assertEqual(
                    self.app._parse_query_string({"query_string": encoded}),
                    expected,
                )
                send = AsyncMock()
                await self.app(
                    self.create_mock_scope(
                        path="/inspect_form",
                        method="POST",
                        headers=[
                            (
                                b"content-type",
                                b"application/x-www-form-urlencoded",
                            )
                        ],
                    ),
                    AsyncMock(
                        return_value={
                            "type": "http.request",
                            "body": encoded,
                            "more_body": False,
                        }
                    ),
                    send,
                )
                self.assertEqual(parsed_bodies[-1], expected)
                send.assert_any_call(
                    {
                        "type": "http.response.body",
                        "body": b"OK",
                        "more_body": False,
                    }
                )


class TestRequestBodyTimeouts(MicroPieTestCase):
    """Tests for configurable non-multipart body receive timeouts."""

    async def test_timeout_resets_for_each_body_chunk(self):
        """A slow body succeeds while each individual chunk arrives in time."""
        self.app = App(body_timeout=0.2)

        async def submit(self, value):
            return value

        setattr(self.app, "submit", submit.__get__(self.app, App))
        chunks = [
            {"type": "http.request", "body": b"val", "more_body": True},
            {"type": "http.request", "body": b"ue=", "more_body": True},
            {"type": "http.request", "body": b"slow", "more_body": False},
        ]

        async def receive():
            await asyncio.sleep(0.08)
            return chunks.pop(0)

        scope = self.create_mock_scope(
            path="/submit",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {"type": "http.response.body", "body": b"slow", "more_body": False}
        )

    async def test_stalled_body_returns_408(self):
        """A receive call exceeding the idle timeout should return 408."""
        self.app = App(body_timeout=0.01)

        async def receive():
            await asyncio.sleep(1)
            return {"type": "http.request", "body": b"value=late", "more_body": False}

        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 408,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_body_timeout_can_be_disabled(self):
        """None should allow a receive call to wait without a framework deadline."""
        self.app = App(body_timeout=None)

        async def submit(self, value):
            return value

        setattr(self.app, "submit", submit.__get__(self.app, App))

        async def receive():
            await asyncio.sleep(0.02)
            return {
                "type": "http.request",
                "body": b"value=received",
                "more_body": False,
            }

        scope = self.create_mock_scope(
            path="/submit",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"received",
                "more_body": False,
            }
        )


class TestRequestBodyLimits(MicroPieTestCase):
    """Tests for declared and streamed request-body limits."""

    async def test_content_length_rejects_oversized_body_before_receive(self):
        """An oversized declared body should be rejected without buffering it."""
        self.app = App(max_body_size=4)
        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[
                (b"content-type", b"application/json"),
                (b"content-length", b"5"),
            ],
        )
        receive = AsyncMock()
        send = AsyncMock()

        await self.app(scope, receive, send)

        receive.assert_not_awaited()
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_invalid_content_length_returns_400(self):
        """Invalid Content-Length values should not bypass early validation."""
        self.app = App(max_body_size=4)
        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[(b"content-length", b"not-a-number")],
        )
        send = AsyncMock()

        await self.app(scope, AsyncMock(), send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"400 Bad Request: Invalid Content-Length",
                "more_body": False,
            }
        )

    async def test_streamed_body_is_counted_without_content_length(self):
        """Chunked bodies should receive 413 as soon as actual bytes exceed the cap."""
        self.app = App(max_body_size=8)
        chunks = [
            {"type": "http.request", "body": b"value=", "more_body": True},
            {"type": "http.request", "body": b"toolong", "more_body": False},
        ]

        async def receive():
            return chunks.pop(0)

        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"413 Payload Too Large",
                "more_body": False,
            }
        )

    async def test_body_at_exact_limit_is_allowed(self):
        """The configured size is inclusive; only larger bodies are rejected."""
        body = b"value=ok"
        self.app = App(max_body_size=len(body))

        async def submit(self, value):
            return value

        setattr(self.app, "submit", submit.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/submit",
            method="POST",
            headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        )
        send = AsyncMock()

        await self.app(
            scope,
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            ),
            send,
        )

        send.assert_any_call(
            {"type": "http.response.body", "body": b"ok", "more_body": False}
        )

    @unittest.skipUnless(MULTIPART_INSTALLED, "multipart package is not installed")
    async def test_multipart_text_field_has_independent_limit(self):
        """A large text field should fail even when total upload size is allowed."""
        body = (
            b"--test-boundary\r\n"
            b'Content-Disposition: form-data; name="note"\r\n\r\n'
            b"12345\r\n"
            b"--test-boundary--\r\n"
        )
        self.app = App(
            max_body_size=len(body) + 1,
            max_form_field_size=4,
        )

        async def upload(self, note):
            return note

        setattr(self.app, "upload", upload.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/upload",
            method="POST",
            headers=[
                (b"content-type", b"multipart/form-data; boundary=test-boundary")
            ],
        )
        send = AsyncMock()

        await asyncio.wait_for(
            self.app(
                scope,
                AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }
                ),
                send,
            ),
            timeout=1,
        )

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"413 Payload Too Large: Multipart form field",
                "more_body": False,
            }
        )

    @unittest.skipUnless(MULTIPART_INSTALLED, "multipart package is not installed")
    async def test_multipart_limit_terminates_open_file_queue(self):
        """A mid-upload 413 should wake a handler already draining the file queue."""
        prefix = (
            b"--test-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
        )
        first_chunk = prefix + b"hello"
        final_chunk = b" world\r\n--test-boundary--\r\n"
        self.app = App(max_body_size=len(first_chunk) + 1)
        handler_saw_failure = asyncio.Event()

        async def upload(self, file):
            try:
                while await file["content"].get() is not None:
                    pass
            except MultipartFileError:
                handler_saw_failure.set()
                raise
            raise AssertionError("A truncated file was reported as complete")

        setattr(self.app, "upload", upload.__get__(self.app, App))
        chunks = [
            {
                "type": "http.request",
                "body": first_chunk,
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": final_chunk,
                "more_body": False,
            },
        ]

        async def receive():
            await asyncio.sleep(0)
            return chunks.pop(0)

        scope = self.create_mock_scope(
            path="/upload",
            method="POST",
            headers=[
                (b"content-type", b"multipart/form-data; boundary=test-boundary")
            ],
        )
        send = AsyncMock()

        await asyncio.wait_for(self.app(scope, receive, send), timeout=1)

        self.assertTrue(handler_saw_failure.is_set())
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    @unittest.skipUnless(MULTIPART_INSTALLED, "multipart package is not installed")
    async def test_stalled_multipart_receive_returns_408(self):
        """Multipart receive calls use the same per-chunk idle timeout."""
        self.app = App(body_timeout=0.01)

        async def upload(self, file):
            return "unreachable"

        setattr(self.app, "upload", upload.__get__(self.app, App))

        async def receive():
            await asyncio.sleep(0.05)
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = self.create_mock_scope(
            path="/upload",
            method="POST",
            headers=[
                (b"content-type", b"multipart/form-data; boundary=test-boundary")
            ],
        )
        send = AsyncMock()

        await asyncio.wait_for(self.app(scope, receive, send), timeout=1)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"408 Request Timeout: Failed to receive body",
                "more_body": False,
            }
        )


class TestMultipartCoordination(MicroPieTestCase):
    """Tests for notification-driven multipart file binding."""

    def multipart_scope(self):
        return self.create_mock_scope(
            path="/upload",
            method="POST",
            headers=[
                (b"content-type", b"multipart/form-data; boundary=test-boundary")
            ],
        )

    async def test_file_notification_starts_handler_before_parse_completion(self):
        """Handlers can drain a file queue while the parser is still active."""
        parser_may_finish = asyncio.Event()
        handler_received_file = asyncio.Event()

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            content = asyncio.Queue(maxsize=file_queue_maxsize)
            request.files["upload"] = {
                "filename": "example.txt",
                "content_type": "text/plain",
                "content": content,
            }
            file_notifications.put_nowait("upload")
            await content.put(b"streamed")
            await content.put(None)
            await parser_may_finish.wait()

        self.app._parse_multipart_into_request = fake_parse

        async def upload(self, upload):
            chunk = await upload["content"].get()
            handler_received_file.set()
            parser_may_finish.set()
            return chunk

        setattr(self.app, "upload", upload.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True):
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        self.assertTrue(handler_received_file.is_set())
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"streamed",
                "more_body": False,
            }
        )

    async def test_parser_completion_wakes_missing_file_waiter(self):
        """A missing file should resolve to a 400 without polling or hanging."""

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            return None

        self.app._parse_multipart_into_request = fake_parse

        async def upload(self, upload):
            return "unreachable"

        setattr(self.app, "upload", upload.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True):
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_parser_failure_is_logged_and_retrieved(self):
        """Parser failures should wake waiters and be consumed by the request task."""

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            raise RuntimeError("broken multipart body")

        self.app._parse_multipart_into_request = fake_parse

        async def upload(self, upload):
            return "unreachable"

        setattr(self.app, "upload", upload.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True), self.assertLogs(
            "micropie", level="ERROR"
        ) as logs:
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        self.assertTrue(
            any(
                "Failed to parse multipart request body" in line
                for line in logs.output
            )
        )
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_early_response_cancels_and_retrieves_parser(self):
        """Middleware short-circuiting should cancel the background parser cleanly."""
        parser_started = asyncio.Event()
        parser_cancelled = asyncio.Event()

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            parser_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                parser_cancelled.set()
                raise

        class RejectUpload(HttpMiddleware):
            async def before_request(self, request):
                await parser_started.wait()
                return {"status_code": 413, "body": "too large"}

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return None

        self.app._parse_multipart_into_request = fake_parse
        self.app.middlewares.append(RejectUpload())
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True):
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        self.assertTrue(parser_cancelled.is_set())
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_large_first_file_does_not_block_second_file_binding(self):
        """Multi-file binding must not depend on the first queue being drained."""

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            self.assertEqual(file_queue_maxsize, 0)
            first = asyncio.Queue(maxsize=file_queue_maxsize)
            request.files["file1"] = {
                "filename": "one.bin",
                "content_type": "application/octet-stream",
                "content": first,
            }
            file_notifications.put_nowait("file1")
            for _ in range(4096):
                await first.put(b"x")
            await first.put(None)

            second = asyncio.Queue(maxsize=file_queue_maxsize)
            request.files["file2"] = {
                "filename": "two.bin",
                "content_type": "application/octet-stream",
                "content": second,
            }
            file_notifications.put_nowait("file2")
            await second.put(b"y")
            await second.put(None)

        self.app._parse_multipart_into_request = fake_parse

        async def upload(self, file1, file2):
            first_size = 0
            while (chunk := await file1["content"].get()) is not None:
                first_size += len(chunk)
            second_chunk = await file2["content"].get()
            return f"{first_size}:{second_chunk.decode()}"

        setattr(self.app, "upload", upload.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True):
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"4096:y",
                "more_body": False,
            }
        )

    async def test_handler_may_return_without_draining_file_queue(self):
        """Parser completion cannot deadlock behind an abandoned file queue."""
        handler_returned = asyncio.Event()

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            content = asyncio.Queue(maxsize=file_queue_maxsize)
            request.files["file"] = {
                "filename": "large.bin",
                "content_type": "application/octet-stream",
                "content": content,
            }
            file_notifications.put_nowait("file")
            await handler_returned.wait()
            for _ in range(4096):
                await content.put(b"x")
            await content.put(None)

        self.app._parse_multipart_into_request = fake_parse

        async def upload(self, file):
            handler_returned.set()
            return "ignored"

        setattr(self.app, "upload", upload.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True):
            await asyncio.wait_for(
                self.app(self.multipart_scope(), AsyncMock(), send), timeout=1
            )

        send.assert_any_call(
            {"type": "http.response.body", "body": b"ignored", "more_body": False}
        )

    async def test_known_parser_failure_prevents_handler_execution(self):
        """An already-failed parser must block query-only handler side effects."""
        parser_failed = asyncio.Event()
        handler_called = False

        async def fake_parse(
            receive,
            boundary,
            request,
            *,
            file_notifications=None,
            file_queue_maxsize=2048,
            max_body_size=None,
            max_form_field_size=None,
            body_timeout=None,
        ):
            parser_failed.set()
            raise RuntimeError("broken multipart body")

        class WaitForFailure(HttpMiddleware):
            async def before_request(self, request):
                await parser_failed.wait()

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return None

        self.app._parse_multipart_into_request = fake_parse
        self.app.middlewares.append(WaitForFailure())

        async def upload(self, value):
            nonlocal handler_called
            handler_called = True
            return value

        setattr(self.app, "upload", upload.__get__(self.app, App))
        scope = self.multipart_scope()
        scope["query_string"] = b"value=unsafe"
        send = AsyncMock()

        with patch("micropie.MULTIPART_INSTALLED", True), self.assertLogs(
            "micropie", level="ERROR"
        ):
            await asyncio.wait_for(self.app(scope, AsyncMock(), send), timeout=1)

        self.assertFalse(handler_called)
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    @unittest.skipUnless(MULTIPART_INSTALLED, "multipart package is not installed")
    async def test_multipart_subapp_handoff_uses_completed_parse(self):
        """A child app must never receive a multipart stream mid-boundary."""
        child = App()

        async def upload(self, file):
            chunks = []
            while (chunk := await file["content"].get()) is not None:
                chunks.append(chunk)
            return b"".join(chunks)

        setattr(child, "upload", upload.__get__(child, App))

        class MountChild(HttpMiddleware):
            async def before_request(self, request):
                request._subapp = child
                request._subapp_path = "/upload"

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return None

        self.app.middlewares.append(MountChild())
        body = (
            b"--test-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"complete file\r\n"
            b"--test-boundary--\r\n"
        )
        send = AsyncMock()

        await asyncio.wait_for(
            self.app(
                self.multipart_scope(),
                AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }
                ),
                send,
            ),
            timeout=1,
        )

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"complete file",
                "more_body": False,
            }
        )


class TestRouting(MicroPieTestCase):
    """Tests for HTTP and WebSocket routing."""

    async def test_app_handler(self):
        """Test handling of a simple HTTP request with query parameter."""

        async def index(self, name="World"):
            return 200, f"Hello, {name}!"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index", query_string=b"name=Test")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"Hello, Test!", "more_body": False}
        )

    async def test_404_response(self):
        """Test 404 response for non-existent route."""
        scope = self.create_mock_scope(path="/nonexistent")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"404 Not Found", "more_body": False}
        )

    async def test_public_internal_attributes_are_not_routable(self):
        """Public App attributes should not be treated as route handlers."""
        for path in ("/session_backend", "/env", "/middlewares"):
            with self.subTest(path=path):
                scope = self.create_mock_scope(path=path)
                receive = AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
                )
                send = AsyncMock()

                await self.app(scope, receive, send)

                send.assert_any_call(
                    {
                        "type": "http.response.start",
                        "status": 404,
                        "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
                    }
                )
                send.assert_any_call(
                    {
                        "type": "http.response.body",
                        "body": b"404 Not Found",
                        "more_body": False,
                    }
                )

    async def test_route_lookup_does_not_execute_properties(self):
        """Non-callable descriptors should be rejected before normal getattr."""

        class PropertyApp(App):
            @property
            def dangerous(self):
                raise AssertionError("route lookup executed a property")

        self.app = PropertyApp()
        scope = self.create_mock_scope(path="/dangerous")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_descriptor_backed_handlers_are_routable_after_binding(self):
        """Method descriptors that bind to callables should remain routable."""

        class DescriptorApp(App):
            def partial_base(self, prefix, suffix=""):
                return f"{prefix}:{suffix}"

            partial = functools.partialmethod(partial_base, "partial")

            @functools.singledispatchmethod
            def dispatch(self, value):
                return f"default:{value}"

        self.app = DescriptorApp()

        for path, body in (
            ("/partial/value", b"partial:value"),
            ("/dispatch/value", b"default:value"),
        ):
            with self.subTest(path=path):
                scope = self.create_mock_scope(path=path)
                receive = AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
                )
                send = AsyncMock()

                await self.app(scope, receive, send)

                send.assert_any_call(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )

    async def test_missing_route_still_falls_back_to_index_with_path_params(self):
        """Unknown routes should still use index when it accepts path params."""

        async def index(self, *parts):
            return "/".join(parts)

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/missing/route")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"missing/route",
                "more_body": False,
            }
        )

    async def test_missing_parameter(self):
        """Test handler with missing required parameter."""

        async def index(self, required_param):
            return "Should not reach here"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"400 Bad Request: Missing required parameter 'required_param'",
                "more_body": False,
            }
        )


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
        receive = AsyncMock(
            side_effect=[
                {"type": "websocket.connect"},
                {"type": "websocket.receive", "text": "Hello"},
                {"type": "websocket.disconnect", "code": 1000},
            ]
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        accept = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "websocket.accept"
        )
        self.assertTrue(
            any(name == b"Set-Cookie" for name, _ in accept["headers"])
        )
        send.assert_any_call({"type": "websocket.send", "text": "Echo: Hello"})
        send.assert_any_call(
            {"type": "websocket.close", "code": 1000, "reason": "Done"}
        )

    async def test_websocket_missing_handler(self):
        """Test WebSocket 1008 response for non-existent route."""
        scope = self.create_mock_scope(path="/nonexistent", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "websocket.close",
                "code": 1008,
                "reason": "No matching WebSocket route",
            }
        )

    async def test_websocket_non_callable_attribute_is_not_routable(self):
        """WebSocket routing should ignore non-callable ws_* attributes."""
        self.app.ws_status = {"connected": False}
        scope = self.create_mock_scope(path="/status", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "websocket.close",
                "code": 1008,
                "reason": "No matching WebSocket route",
            }
        )

    async def test_session_values_do_not_bind_websocket_parameters(self):
        """WebSocket arguments must not fall through to session state."""

        async def ws_transfer(self, ws, user_id):
            await ws.accept()

        setattr(self.app, "ws_transfer", ws_transfer.__get__(self.app, App))
        scope = self.create_mock_scope(path="/transfer", scope_type="websocket")
        scope["session"] = {"user_id": "trusted-user"}
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "websocket.close",
                "code": 1008,
                "reason": "Missing required parameter 'user_id'",
            }
        )

    async def test_malformed_websocket_query_is_tolerated(self):
        """WebSocket query parsing should use the same permissive behavior."""

        async def ws_echo(self, ws, name):
            await ws.accept()
            await ws.send_text(name)
            await ws.close()

        setattr(self.app, "ws_echo", ws_echo.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/echo",
            query_string=b"name=%ZZ",
            scope_type="websocket",
        )
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call({"type": "websocket.send", "text": "%ZZ"})

    async def test_websocket_cookie_respects_secure_configuration(self):
        """WebSocket handshake cookies should use the App cookie policy."""
        self.app = App(session_cookie_secure=False)

        async def ws_cookie(self, ws):
            await ws.accept(session_id=VALID_SESSION_ID)
            await ws.close()

        setattr(self.app, "ws_cookie", ws_cookie.__get__(self.app, App))
        scope = self.create_mock_scope(path="/cookie", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        accept = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "websocket.accept"
        )
        cookie = next(
            value for name, value in accept["headers"] if name == b"Set-Cookie"
        )
        self.assertIn(b"HttpOnly", cookie)
        self.assertNotIn(b"Secure", cookie)

    async def test_websocket_accept_uses_custom_session_id_validator(self):
        """Explicit non-UUID IDs are allowed by an application's policy."""
        self.app = App(
            session_id_factory=lambda: "signed.fresh",
            session_id_validator=lambda value: (
                value if value.startswith("signed.") else None
            ),
        )

        async def ws_cookie(self, ws):
            await ws.accept(session_id="signed.explicit")
            await ws.close()

        setattr(self.app, "ws_cookie", ws_cookie.__get__(self.app, App))
        send = AsyncMock()

        await self.app(
            self.create_mock_scope(path="/cookie", scope_type="websocket"),
            AsyncMock(return_value={"type": "websocket.connect"}),
            send,
        )

        accept = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "websocket.accept"
        )
        cookie = next(
            value for name, value in accept["headers"] if name == b"Set-Cookie"
        )
        self.assertIn(b"session_id=signed.explicit", cookie)

    async def test_websocket_session_uses_app_timeout(self):
        """WebSocket session saves should receive the configured timeout."""
        backend = CountingSessionBackend()
        self.app = App(session_backend=backend, session_timeout=321)

        async def ws_session(self, ws):
            self.request.session["user"] = "alice"
            await ws.accept()
            await ws.close()

        setattr(self.app, "ws_session", ws_session.__get__(self.app, App))
        scope = self.create_mock_scope(path="/session", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(backend.save_calls[-1][2], 321)
        accept = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "websocket.accept"
        )
        cookie = next(
            value for name, value in accept["headers"] if name == b"Set-Cookie"
        ).decode("ascii")
        cookie_session_id = cookie.split(";", 1)[0].split("=", 1)[1]
        self.assertEqual(cookie_session_id, backend.save_calls[-1][0])
        self.assertEqual(backend.sessions[cookie_session_id], {"user": "alice"})

    async def test_websocket_rotates_unknown_client_session_id(self):
        """A planted UUID should be replaced during the WebSocket handshake."""
        backend = CountingSessionBackend()
        self.app = App(session_backend=backend)

        async def ws_login(self, ws):
            await ws.accept()
            self.request.session["user_id"] = 42
            await ws.close()

        setattr(self.app, "ws_login", ws_login.__get__(self.app, App))
        scope = self.create_mock_scope(
            path="/login",
            scope_type="websocket",
            headers=[
                (
                    b"cookie",
                    f"session_id={ATTACKER_SESSION_ID}".encode("ascii"),
                )
            ],
        )
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await self.app(scope, receive, send)

        accept = next(
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "websocket.accept"
        )
        cookie = next(
            value for name, value in accept["headers"] if name == b"Set-Cookie"
        ).decode("ascii")
        new_session_id = cookie.split(";", 1)[0].split("=", 1)[1]
        self.assertNotEqual(new_session_id, ATTACKER_SESSION_ID)
        self.assertEqual(uuid.UUID(new_session_id).version, 4)
        self.assertNotIn(ATTACKER_SESSION_ID, backend.sessions)
        self.assertEqual(backend.sessions[new_session_id], {"user_id": 42})

    async def test_websocket_handler_exception_is_logged(self):
        """WebSocket handler failures should include traceback logging."""

        async def ws_broken(self, ws):
            raise RuntimeError("websocket boom")

        setattr(self.app, "ws_broken", ws_broken.__get__(self.app, App))
        scope = self.create_mock_scope(path="/broken", scope_type="websocket")
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        with self.assertLogs("micropie", level="ERROR") as logs:
            await self.app(scope, receive, send)

        self.assertTrue(any(record.exc_info for record in logs.records))
        send.assert_any_call(
            {
                "type": "websocket.close",
                "code": 1011,
                "reason": "Internal server error",
            }
        )


class TestMiddleware(MicroPieTestCase):
    """Tests for HTTP and WebSocket middleware."""

    async def test_http_middleware(self):
        """Test HTTP middleware before and after request."""

        class TestMiddleware(HttpMiddleware):
            async def before_request(self, request):
                request.custom_data = "set_by_middleware"
                return None

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return {
                    "status_code": 201,
                    "body": f"{response_body} + middleware",
                    "headers": extra_headers,
                }

        self.app.middlewares.append(TestMiddleware())

        async def index(self):
            return f"Data: {self.request.custom_data}"

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"Data: set_by_middleware + middleware",
                "more_body": False,
            }
        )

    async def test_partial_before_request_response_uses_defaults(self):
        """A partial short-circuit mapping should not raise KeyError."""

        class NoContent(HttpMiddleware):
            async def before_request(self, request):
                return {"status_code": 204}

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return None

        self.app.middlewares.append(NoContent())
        send = AsyncMock()

        await self.app(
            self.create_mock_scope(),
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            ),
            send,
        )

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"", "more_body": False}
        )

    async def test_json_subapp_handoff_preserves_json_namespace(self):
        """Child apps receive JSON through Request.json(), not body_params."""
        child = App()

        async def submit(self):
            return {
                "value": self.request.json("value"),
                "body_params": self.request.body_params,
            }

        setattr(child, "submit", submit.__get__(child, App))

        class MountChild(HttpMiddleware):
            async def before_request(self, request):
                request._subapp = child
                request._subapp_path = "/submit"

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                return None

        self.app.middlewares.append(MountChild())
        send = AsyncMock()

        await self.app(
            self.create_mock_scope(
                path="/mounted/submit",
                method="POST",
                headers=[(b"content-type", b"application/json")],
            ),
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": b'{"value": 7}',
                    "more_body": False,
                }
            ),
            send,
        )

        body = next(
            call[0][0]["body"]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.body"
        )
        self.assertEqual(std_json.loads(body), {"value": 7, "body_params": {}})


class TestResponseHandling(MicroPieTestCase):
    """Tests for response handling and edge cases."""

    async def test_json_handling(self):
        """Test JSON request and response handling."""

        async def json_handler(self):
            return self.request.json()

        setattr(self.app, "json_handler", json_handler.__get__(self.app, App))

        scope = self.create_mock_scope(
            path="/json_handler",
            method="POST",
            headers=[(b"content-type", b"application/json")],
        )
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": b'{"key": "value"}',
                "more_body": False,
            }
        )
        send = AsyncMock()

        with patch("micropie.json") as mock_json:
            mock_json.loads.return_value = {"key": "value"}
            mock_json.dumps.return_value = b'{"key": "value"}'

            await self.app(scope, receive, send)

            mock_json.loads.assert_called_once()
            mock_json.dumps.assert_called_once()
            send.assert_any_call(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"Content-Type", b"application/json")],
                }
            )
            send.assert_any_call(
                {
                    "type": "http.response.body",
                    "body": b'{"key": "value"}',
                    "more_body": False,
                }
            )

    async def test_json_response_type_is_stable_for_middleware(self):
        """Middleware sees text regardless of the selected JSON implementation."""
        seen_types = []

        class ObserveBody(HttpMiddleware):
            async def before_request(self, request):
                return None

            async def after_request(
                self, request, status_code, response_body, extra_headers
            ):
                seen_types.append(type(response_body))

        self.app.middlewares.append(ObserveBody())

        async def index(self):
            return {"ok": True}

        setattr(self.app, "index", index.__get__(self.app, App))
        send = AsyncMock()

        with patch("micropie.json.dumps", return_value=b'{"ok":true}'):
            await self.app(
                self.create_mock_scope(),
                AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
                ),
                send,
            )

        self.assertEqual(seen_types, [str])
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b'{"ok":true}',
                "more_body": False,
            }
        )

    async def test_json_arguments_keep_native_types_and_form_namespace(self):
        """JSON binding should not stringify or mirror values into form data."""
        captured = {}

        async def json_native(self, profile, tags, enabled, count, nullable):
            captured.update(
                {
                    "profile": profile,
                    "tags": tags,
                    "enabled": enabled,
                    "count": count,
                    "nullable": nullable,
                    "body_params": self.request.body_params,
                    "form_profile": self.request.form("profile", "not-form-data"),
                }
            )
            return "OK"

        setattr(self.app, "json_native", json_native.__get__(self.app, App))
        payload = {
            "profile": {"id": 7},
            "tags": ["one", "two"],
            "enabled": True,
            "count": 3,
            "nullable": None,
        }
        scope = self.create_mock_scope(
            path="/json_native",
            method="POST",
            headers=[(b"content-type", b"application/json")],
        )
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": std_json.dumps(payload).encode("utf-8"),
                "more_body": False,
            }
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        self.assertEqual(captured["profile"], {"id": 7})
        self.assertEqual(captured["tags"], ["one", "two"])
        self.assertIs(captured["enabled"], True)
        self.assertEqual(captured["count"], 3)
        self.assertIsNone(captured["nullable"])
        self.assertEqual(captured["body_params"], {})
        self.assertEqual(captured["form_profile"], "not-form-data")
        send.assert_any_call(
            {"type": "http.response.body", "body": b"OK", "more_body": False}
        )

    async def test_invalid_json(self):
        """Test handling of invalid JSON in POST request."""
        scope = self.create_mock_scope(
            path="/index",
            method="POST",
            headers=[(b"content-type", b"application/json")],
        )
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": b"{invalid}",
                "more_body": False,
            }
        )
        send = AsyncMock()

        await self.app(scope, receive, send)

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )
        send.assert_any_call(
            {
                "type": "http.response.body",
                "body": b"400 Bad Request: Bad JSON",
                "more_body": False,
            }
        )

    async def test_http_handler_exception_is_logged(self):
        """HTTP handler failures should include traceback logging."""

        async def index(self):
            raise RuntimeError("http boom")

        setattr(self.app, "index", index.__get__(self.app, App))
        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        with self.assertLogs("micropie", level="ERROR") as logs:
            await self.app(scope, receive, send)

        self.assertTrue(any(record.exc_info for record in logs.records))
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_header_injection(self):
        """Test protection against header injection."""

        async def index(self):
            return 200, "Test", [("Bad-Header", "value\r\nInject: malicious")]

        setattr(self.app, "index", index.__get__(self.app, App))

        scope = self.create_mock_scope(path="/index")
        receive = AsyncMock(
            return_value={"type": "http.request", "body": b"", "more_body": False}
        )
        send = AsyncMock()

        with self.assertLogs("micropie", level="WARNING") as logs:
            await self.app(scope, receive, send)

        self.assertTrue(
            any("Rejected response header" in line for line in logs.output)
        )

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
            "Malicious header should be filtered out",
        )
        send.assert_any_call(
            {"type": "http.response.body", "body": b"Test", "more_body": False}
        )

    async def test_non_latin1_header_is_rejected_before_response_start(self):
        """An unencodable header should be skipped instead of crashing ASGI."""

        async def index(self):
            return 200, "OK", [("X-Snowman", "☃")]

        setattr(self.app, "index", index.__get__(self.app, App))
        send = AsyncMock()

        with self.assertLogs("micropie", level="WARNING"):
            await self.app(
                self.create_mock_scope(),
                AsyncMock(
                    return_value={
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
                ),
                send,
            )

        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
            }
        )

    async def test_sync_generator_advances_off_event_loop(self):
        """Blocking synchronous generator steps run in a worker thread."""
        event_loop_thread = threading.get_ident()
        generator_threads = []

        def chunks():
            generator_threads.append(threading.get_ident())
            yield "chunk"

        async def index(self):
            return chunks()

        setattr(self.app, "index", index.__get__(self.app, App))
        send = AsyncMock()

        await self.app(
            self.create_mock_scope(),
            AsyncMock(
                return_value={
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            ),
            send,
        )

        self.assertTrue(generator_threads)
        self.assertNotEqual(generator_threads[0], event_loop_thread)

    async def test_stream_completion_cancels_pending_receive(self):
        """Completing a streamed response must not orphan receive()."""
        receive_cancelled = asyncio.Event()

        async def stream():
            yield b"done"

        async def index(self):
            return stream()

        async def receive():
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                receive_cancelled.set()
                raise

        setattr(self.app, "index", index.__get__(self.app, App))

        await asyncio.wait_for(
            self.app(self.create_mock_scope(), receive, AsyncMock()), timeout=1
        )

        self.assertTrue(receive_cancelled.is_set())

    async def test_redirect(self):
        """Test redirect response generation."""
        location = "/new-page"
        extra_headers = [("X-Custom", "Value")]
        status_code, body, headers = self.app._redirect(location, extra_headers)
        self.assertEqual(status_code, 302, "Redirect should return 302 status")
        self.assertEqual(body, "", "Redirect body should be empty")
        self.assertIn(("Location", location), headers, "Location header should be set")
        self.assertIn(
            ("X-Custom", "Value"), headers, "Extra headers should be included"
        )
        _, _, unicode_headers = self.app._redirect("/search?q=snow man ☃")
        self.assertIn(
            ("Location", "/search?q=snow%20man%20%E2%98%83"), unicode_headers
        )


class TestOptionalDependencies(MicroPieTestCase):
    """Tests for behavior with missing optional dependencies."""

    async def test_no_multipart_installed(self):
        """Test behavior when multipart is not installed."""
        with patch("micropie.MULTIPART_INSTALLED", False), self.assertLogs(
            "micropie", level="ERROR"
        ) as logs:
            scope = self.create_mock_scope(
                path="/index",
                method="POST",
                headers=[
                    (b"content-type", b"multipart/form-data; boundary=----boundary")
                ],
            )
            receive = AsyncMock(
                return_value={"type": "http.request", "body": b"", "more_body": False}
            )
            send = AsyncMock()

            await self.app(scope, receive, send)

            self.assertTrue(
                any("requires the 'multipart' package" in line for line in logs.output)
            )

            send.assert_any_call(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
                }
            )
            send.assert_any_call(
                {
                    "type": "http.response.body",
                    "body": b"500 Internal Server Error",
                    "more_body": False,
                }
            )

    async def test_no_jinja_installed(self):
        """Test behavior when Jinja2 is not installed."""
        with patch("micropie.JINJA_INSTALLED", False), self.assertLogs(
            "micropie", level="ERROR"
        ) as logs:

            async def index(self):
                return await self._render_template("test.html")

            setattr(self.app, "index", index.__get__(self.app, App))

            scope = self.create_mock_scope(path="/index")
            receive = AsyncMock(
                return_value={"type": "http.request", "body": b"", "more_body": False}
            )
            send = AsyncMock()

            await self.app(scope, receive, send)

            self.assertTrue(
                any("requires the 'jinja2' package" in line for line in logs.output)
            )

            send.assert_any_call(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"Content-Type", b"text/html; charset=utf-8")],
                }
            )
            send.assert_any_call(
                {
                    "type": "http.response.body",
                    "body": b"500 Internal Server Error: Jinja2 not installed.",
                    "more_body": False,
                }
            )


if __name__ == "__main__":
    unittest.main()
