import asyncio
import os
import shutil
import time
import uuid
import pytest
from MicroPie import App, Request, WebSocket, HttpMiddleware, InMemorySessionBackend
from urllib.parse import parse_qs

# Mock MULTIPART_INSTALLED and JINJA_INSTALLED for testing optional dependencies
MULTIPART_INSTALLED = True
JINJA_INSTALLED = True

# Import optional dependencies safely
try:
    import aiofiles
    from multipart import PushMultipartParser, MultipartSegment
except ImportError:
    pass

try:
    from jinja2 import Environment
except ImportError:
    pass

# Setup fixture for uploads directory
@pytest.fixture(autouse=True)
def setup_uploads():
    upload_dir = "uploads"
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
    yield
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

# Setup fixture for templates directory
@pytest.fixture
def setup_templates():
    os.makedirs("templates", exist_ok=True)
    yield
    if os.path.exists("templates"):
        shutil.rmtree("templates")

# Test 1: Basic HTTP GET Request
@pytest.mark.asyncio
async def test_basic_get_request():
    class TestApp(App):
        async def index(self):
            return "Hello, World!"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["type"] == "http.response.body"
    assert sent_messages[1]["body"] == b"Hello, World!"

# Test 2: HTTP GET with Path Parameters
@pytest.mark.asyncio
async def test_get_with_path_params():
    class TestApp(App):
        async def user(self, user_id):
            return f"User {user_id}"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/user/123",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"User 123"

# Test 3: HTTP GET with Query Parameters
@pytest.mark.asyncio
async def test_get_with_query_params():
    class TestApp(App):
        async def search(self, query):
            return f"Search for {query}"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/search",
        "headers": [],
        "query_string": b"query=python",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"Search for python"

# Test 4: HTTP POST with Form Data
@pytest.mark.asyncio
async def test_post_with_form_data():
    class TestApp(App):
        async def login(self, username, password):
            return "Login successful" if username == "admin" and password == "secret" else ("Invalid credentials", 401)

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"username=admin&password=secret", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"Login successful"

# Test 5: HTTP POST with JSON Data
@pytest.mark.asyncio
async def test_post_with_json_data():
    class TestApp(App):
        async def create_user(self, name):
            return f"User {name} created"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/create_user",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b'{"name": "Alice"}', "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"User Alice created"

# Test 6: HTTP POST with Multipart File Upload
@pytest.mark.asyncio
async def test_post_with_multipart_file_upload():
    class TestApp(App):
        async def upload(self, file):
            return f"File {file['filename']} uploaded to {file['saved_path']}"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [(b"content-type", b"multipart/form-data; boundary=boundary")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Hello, World!\r\n"
        b"--boundary--\r\n"
    )

    async def mock_receive():
        return {"type": "http.request", "body": body, "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["status"] == 200
    assert b"File test.txt uploaded to" in sent_messages[1]["body"]
    files = os.listdir("uploads")
    assert len(files) == 1
    with open(os.path.join("uploads", files[0]), "rb") as f:
        assert f.read() == b"Hello, World!"

# Test 7: Session Management
@pytest.mark.asyncio
async def test_session_management():
    class TestApp(App):
        async def login(self, username):
            request = self.request
            request.session["username"] = username
            return "Logged in"

        async def profile(self):
            request = self.request
            return f"Welcome, {request.session.get('username', 'Guest')}"

    app = TestApp()
    scope_login = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [],
        "query_string": b"username=alice",
    }
    sent_messages_login = []

    async def mock_send_login(message):
        sent_messages_login.append(message)

    async def mock_receive_login():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope_login, mock_receive_login, mock_send_login)
    assert sent_messages_login[0]["status"] == 200

    session_id = [h[1].decode().split(";")[0].split("=")[1] for h in sent_messages_login[0]["headers"] if h[0] == b"Set-Cookie"][0]
    scope_profile = {
        "type": "http",
        "method": "GET",
        "path": "/profile",
        "headers": [(b"cookie", f"session_id={session_id}".encode())],
        "query_string": b"",
    }
    sent_messages_profile = []

    async def mock_send_profile(message):
        sent_messages_profile.append(message)

    async def mock_receive_profile():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope_profile, mock_receive_profile, mock_send_profile)
    assert sent_messages_profile[0]["status"] == 200
    assert sent_messages_profile[1]["body"] == b"Welcome, alice"

# Test 8: WebSocket Connection
@pytest.mark.asyncio
async def test_websocket_connection():
    class TestApp(App):
        async def ws_echo(self, websocket, path_params):
            await websocket.accept()
            message = await websocket.receive_text()
            await websocket.send_text(f"Echo: {message}")
            await websocket.close()

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/echo",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []
    received_messages = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": "Hello"},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return received_messages.pop(0)

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 3
    assert sent_messages[0]["type"] == "websocket.accept"
    assert sent_messages[1]["type"] == "websocket.send"
    assert sent_messages[1]["text"] == "Echo: Hello"
    assert sent_messages[2]["type"] == "websocket.close"
    assert sent_messages[2]["code"] == 1000

# Test 9: HTTP Middleware
@pytest.mark.asyncio
async def test_http_middleware():
    class CustomHeaderMiddleware(HttpMiddleware):
        async def before_request(self, request):
            pass

        async def after_request(self, request, status_code, response_body, extra_headers):
            extra_headers.append(("X-Custom-Header", "Test"))
            return {"headers": extra_headers}

    class TestApp(App):
        async def index(self):
            return "Hello"

    app = TestApp()
    app.middlewares.append(CustomHeaderMiddleware())
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert any(h[0] == b"X-Custom-Header" and h[1] == b"Test" for h in sent_messages[0]["headers"])

# Test 10: Template Rendering
@pytest.mark.asyncio
async def test_template_rendering(setup_templates):
    with open("templates/hello.html", "w") as f:
        f.write("Hello, {{ name }}!")

    class TestApp(App):
        async def index(self):
            return await self._render_template("hello.html", name="World")

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"Hello, World!"

# Test 11: 404 Not Found
@pytest.mark.asyncio
async def test_404_not_found():
    class TestApp(App):
        pass

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/nonexistent",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 404
    assert sent_messages[1]["body"] == b"404 Not Found"

# Test 12: 400 Bad Request (Missing Parameter)
@pytest.mark.asyncio
async def test_400_missing_parameter():
    class TestApp(App):
        async def index(self, required_param):
            return "Should not reach here"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 400
    assert b"Missing required parameter" in sent_messages[1]["body"]

# Test 13: 500 Internal Server Error
@pytest.mark.asyncio
async def test_500_internal_server_error():
    class TestApp(App):
        async def index(self):
            raise Exception("Test error")

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 500
    assert sent_messages[1]["body"] == b"500 Internal Server Error"

# Test 14: WebSocket Error Handling
@pytest.mark.asyncio
async def test_websocket_error_handling():
    class TestApp(App):
        async def ws_index(self, websocket, path_params):
            raise Exception("Test error")

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "websocket.connect"}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "websocket.close"
    assert sent_messages[0]["code"] == 1011

# Test 15: Parse Cookies
def test_parse_cookies():
    app = App()
    cookies = app._parse_cookies("session_id=abc123; user=alice")
    assert cookies == {"session_id": "abc123", "user": "alice"}

# Test 16: Redirect
@pytest.mark.asyncio
async def test_redirect():
    class TestApp(App):
        async def index(self):
            return self._redirect("/new_location")

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 302
    assert any(h[0] == b"Location" and h[1] == b"/new_location" for h in sent_messages[0]["headers"])

# Test 17: In-Memory Session Backend
@pytest.mark.asyncio
async def test_in_memory_session_backend():
    backend = InMemorySessionBackend()
    session_id = "test_session"
    data = {"key": "value"}
    await backend.save(session_id, data, 3600)
    loaded_data = await backend.load(session_id)
    assert loaded_data == data
    # Simulate session timeout
    backend.last_access[session_id] = time.time() - 8 * 3600 - 1
    assert await backend.load(session_id) == {}

# Test 18: Synchronous Handler
@pytest.mark.asyncio
async def test_synchronous_handler():
    class TestApp(App):
        def index(self):
            return "Sync Hello"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"Sync Hello"

# Test 19: Asynchronous Streaming Response
@pytest.mark.asyncio
async def test_async_streaming_response():
    class TestApp(App):
        async def stream(self):
            async def generate():
                yield "Chunk 1"
                await asyncio.sleep(0.1)
                yield "Chunk 2"
            return generate()

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/stream",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 4
    assert sent_messages[1]["body"] == b"Chunk 1"
    assert sent_messages[2]["body"] == b"Chunk 2"
    assert sent_messages[3]["body"] == b""

# Test 20: Synchronous Generator Response
@pytest.mark.asyncio
async def test_sync_generator_response():
    class TestApp(App):
        def stream(self):
            def generate():
                yield "Chunk 1"
                yield "Chunk 2"
            return generate()

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/stream",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 4
    assert sent_messages[1]["body"] == b"Chunk 1"
    assert sent_messages[2]["body"] == b"Chunk 2"

# Test 21: JSON Response
@pytest.mark.asyncio
async def test_json_response():
    class TestApp(App):
        async def data(self):
            return {"key": "value"}

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/data",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert any(h[0] == b"Content-Type" and h[1] == b"application/json" for h in sent_messages[0]["headers"])
    assert sent_messages[1]["body"] == b'{"key": "value"}'

# Test 22: Protected Path (Starting with '_')
@pytest.mark.asyncio
async def test_protected_path():
    class TestApp(App):
        async def _hidden(self):
            return "Should not reach here"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/_hidden",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 404

# Test 23: WebSocket Protected Path
@pytest.mark.asyncio
async def test_websocket_protected_path():
    class TestApp(App):
        async def _ws_hidden(self, websocket, path_params):
            pass

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/_hidden",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "websocket.connect"}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["type"] == "websocket.close"
    assert sent_messages[0]["code"] == 1008

# Test 24: Invalid JSON
@pytest.mark.asyncio
async def test_invalid_json():
    class TestApp(App):
        async def index(self):
            pass

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/index",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"{invalid}", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 400
    assert sent_messages[1]["body"] == b"400 Bad Request: Bad JSON"

# Test 25: Header Injection Prevention
@pytest.mark.asyncio
async def test_header_injection_prevention():
    class TestApp(App):
        async def index(self):
            return "Hello", 200, [("X-Test", "Value\nInjection")]

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert not any(b"\n" in h[1] for h in sent_messages[0]["headers"])

# Test 26: Missing Jinja2 Dependency
@pytest.mark.asyncio
async def test_missing_jinja2(monkeypatch):
    monkeypatch.setattr("MicroPie.JINJA_INSTALLED", False)
    class TestApp(App):
        async def index(self):
            return await self._render_template("hello.html", name="World")

    app = TestApp()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 500
    assert sent_messages[1]["body"] == b"500 Internal Server Error"

# Test 27: Missing Multipart Dependency
@pytest.mark.asyncio
async def test_missing_multipart(monkeypatch):
    monkeypatch.setattr("MicroPie.MULTIPART_INSTALLED", False)
    class TestApp(App):
        async def upload(self, file):
            return "Should not reach here"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [(b"content-type", b"multipart/form-data; boundary=boundary")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 500
    assert sent_messages[1]["body"] == b"500 Internal Server Error"

# Test 28: WebSocket Send JSON
@pytest.mark.asyncio
async def test_websocket_send_json():
    class TestApp(App):
        async def ws_json(self, websocket, path_params):
            await websocket.accept()
            await websocket.send_json({"message": "Hello"})
            await websocket.close()

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/json",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "websocket.connect"}

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 3
    assert sent_messages[0]["type"] == "websocket.accept"
    assert sent_messages[1]["type"] == "websocket.send"
    assert sent_messages[1]["text"] == '{"message": "Hello"}'
    assert sent_messages[2]["type"] == "websocket.close"

# Test 29: WebSocket Receive JSON
@pytest.mark.asyncio
async def test_websocket_receive_json():
    class TestApp(App):
        async def ws_json(self, websocket, path_params):
            await websocket.accept()
            data = await websocket.receive_json()
            await websocket.send_text(f"Received: {data['message']}")
            await websocket.close()

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/json",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []
    received_messages = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": '{"message": "Hello"}'},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return received_messages.pop(0)

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 3
    assert sent_messages[0]["type"] == "websocket.accept"
    assert sent_messages[1]["type"] == "websocket.send"
    assert sent_messages[1]["text"] == "Received: Hello"
    assert sent_messages[2]["type"] == "websocket.close"

# Test 30: WebSocket Disconnect
@pytest.mark.asyncio
async def test_websocket_disconnect():
    class TestApp(App):
        async def ws_disconnect(self, websocket, path_params):
            await websocket.accept()
            await websocket.receive_text()  # Should raise ConnectionError
            await websocket.close()

    app = TestApp()
    scope = {
        "type": "websocket",
        "path": "/disconnect",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []
    received_messages = [
        {"type": "websocket.connect"},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return received_messages.pop(0)

    await app(scope, mock_receive, mock_send)
    assert len(sent_messages) == 2
    assert sent_messages[0]["type"] == "websocket.accept"
    assert sent_messages[1]["type"] == "websocket.close"

# Test 31: Middleware Before Request Early Exit
@pytest.mark.asyncio
async def test_middleware_before_request_early_exit():
    class EarlyExitMiddleware(HttpMiddleware):
        async def before_request(self, request):
            return {"status_code": 403, "body": "Forbidden"}

        async def after_request(self, request, status_code, response_body, extra_headers):
            pass

    class TestApp(App):
        async def index(self):
            return "Should not reach here"

    app = TestApp()
    app.middlewares.append(EarlyExitMiddleware())
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    async def mock_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 403
    assert sent_messages[1]["body"] == b"Forbidden"

# Test 32: Empty Cookie Header
def test_empty_cookie_header():
    app = App()
    cookies = app._parse_cookies("")
    assert cookies == {}

# Test 33: Multipart Form Data Without File
@pytest.mark.asyncio
async def test_multipart_form_data_without_file():
    class TestApp(App):
        async def form(self, field):
            return f"Field: {field[0]}"

    app = TestApp()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/form",
        "headers": [(b"content-type", b"multipart/form-data; boundary=boundary")],
        "query_string": b"",
    }
    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="field"\r\n'
        b"\r\n"
        b"test_value\r\n"
        b"--boundary--\r\n"
    )

    async def mock_receive():
        return {"type": "http.request", "body": body, "more_body": False}

    await app(scope, mock_receive, mock_send)
    assert sent_messages[0]["status"] == 200
    assert sent_messages[1]["body"] == b"Field: test_value"
