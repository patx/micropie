[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**

**MicroPie** is a fast, lightweight, modern Python web framework that supports asynchronous web applications with built-in HTTP and WebSocket handling. Designed with **flexibility** and **simplicity** in mind, MicroPie enables you to handle high-concurrency applications with ease, supporting both traditional HTTP requests and real-time bidirectional communication via WebSockets.

### **Key Features**
- 🔄 **Routing:** Automatic mapping of URLs to functions with support for dynamic and query parameters for HTTP and WebSocket endpoints.
- 🔒 **Sessions:** Simple, pluggable session management using cookies.
- 🎨 **Templates:** Jinja2, if installed, for rendering dynamic HTML pages.
- ⚙️ **Middleware:** Support for custom request middleware enabling functions like rate limiting, authentication, logging, and more.
- ✨ **ASGI-Powered:** Built with asynchronous support for modern web servers like Uvicorn and Daphne, enabling high concurrency for both HTTP and WebSockets.
- 🌐 **WebSocket Support:** Native WebSocket handling for real-time applications, with easy-to-use `WebSocket` class and `ws_` prefixed handlers.
- 🛠️ **Lightweight Design:** Only optional dependencies for flexibility and faster development/deployment.
- ⚡ **Blazing Fast:** Check out how MicroPie compares to other popular ASGI frameworks below!

### **Useful Links**
- **Homepage**: [patx.github.io/micropie](https://patx.github.io/micropie)
- **API Reference**: [README.md#api-documentation](https://github.com/patx/micropie/blob/main/README.md#api-documentation)
- **PyPI Page**: [pypi.org/project/MicroPie](https://pypi.org/project/MicroPie/)
- **GitHub Project**: [github.com/patx/micropie](https://github.com/patx/micropie)
- **File Issue/Request**: [github.com/patx/micropie/issues](https://github.com/patx/micropie/issues)
- **Example Applications**: [github.com/patx/micropie/tree/main/examples](https://github.com/patx/micropie/tree/main/examples)
- **Introduction Lightning Talk**: [Introduction to MicroPie on YouTube](https://www.youtube.com/watch?v=BzkscTLy1So)

## **Installing MicroPie**

### **Installation**
Install MicroPie with all optional dependencies via pip:
```bash
pip install micropie[all]
```
This will install MicroPie along with `jinja2` for template rendering and `multipart`/`aiofiles` for parsing multipart form data.

### **Minimal Setup**
You can also install MicroPie without ANY dependencies via pip:
```bash
pip install micropie
```

For an ultra-minimalistic approach, download the standalone script:

[MicroPie.py](https://raw.githubusercontent.com/patx/micropie/refs/heads/main/MicroPie.py)

Place it in your project directory, and you are good to go. Note that `jinja2` must be installed separately to use the `_render_template` method and/or `multipart` & `aiofiles` for handling file uploads (the `_parse_multipart` method), but these are optional. To install the optional dependencies use:
```bash
pip install jinja2 multipart aiofiles
```

### **Install an ASGI Web Server**
To test and deploy your apps, you will need an ASGI web server like Uvicorn, Hypercorn, or Daphne. For WebSocket support, ensure the server supports WebSockets (Uvicorn requires `websockets` or `wsproto`). Install `uvicorn` with WebSocket support:
```bash
pip install 'uvicorn[standard]'
```

## **Getting Started**

### **Create Your First ASGI App**

Save the following as `app.py`:
```python
from MicroPie import App

class MyApp(App):
    async def index(self):
        return "Welcome to MicroPie ASGI."

app = MyApp()
```
Run the server with:
```bash
uvicorn app:app
```
Access your app at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## **Core Features**

### **1. Flexible HTTP Routing for GET Requests**
MicroPie automatically maps URLs to methods within your `App` class. Routes can be defined as either synchronous or asynchronous functions, offering great flexibility.

For GET requests, pass data through query strings or URL path segments, automatically mapped to method arguments.
```python
class MyApp(App):
    async def greet(self, name="Guest"):
        return f"Hello, {name}!"

    async def hello(self):
        name = self.request.query_params.get("name", [None])[0]
        return f"Hello {name}!"
```
**Access:**
- [http://127.0.0.1:8000/greet?name=Alice](http://127.0.0.1:8000/greet?name=Alice) returns `Hello, Alice!`, same as [http://127.0.0.1:8000/greet/Alice](http://127.0.0.1:8000/greet/Alice) returns `Hello, Alice!`.
- [http://127.0.0.1:8000/hello/Alice](http://127.0.0.1:8000/hello/Alice) returns a `500 Internal Server Error` because it is expecting [http://127.0.0.1:8000/hello?name=Alice](http://127.0.0.1:8000/hello?name=Alice), which returns `Hello Alice!`

### **2. Flexible HTTP POST Request Handling**
MicroPie supports handling form data submitted via HTTP POST requests. Form data is automatically mapped to method arguments and can handle default values and raw/JSON POST data:
```python
class MyApp(App):
    async def submit_default_values(self, username="Anonymous"):
        return f"Form submitted by: {username}"

    async def submit_catch_all(self):
        username = self.request.body_params.get("username", ["Anonymous"])[0]
        return f"Submitted by: {username}"
```

By default, MicroPie's route handlers can accept any request method. You can check the request method (and other request-specific details) in the handler with `self.request.method`. See how to handle POST JSON data at [examples/api](https://github.com/patx/micropie/tree/main/examples/api).

### **3. Native WebSocket Support**
MicroPie includes built-in WebSocket support for real-time, bidirectional communication. Define WebSocket handlers using methods prefixed with `ws_` (e.g., `ws_chat`). The `WebSocket` class provides methods to accept connections, send/receive text or JSON, and close connections.

```python
from MicroPie import App, WebSocket
from typing import List

class MyApp(App):
    def __init__(self):
        super().__init__()
        self.active_connections: List[WebSocket] = []

    async def index(self):
        return await self._render_template("chat.html")

    async def ws_chat(self, websocket: WebSocket, path_params: List[str]):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            while True:
                message = await websocket.receive_text()
                for conn in self.active_connections:
                    await conn.send_text(f"User: {message}")
        except:
            self.active_connections.remove(websocket)
            await websocket.close()
```

**Access:**
- Serve the chat interface at [http://127.0.0.1:8000](http://127.0.0.1:8000).
- Connect to the WebSocket endpoint at [ws://127.0.0.1:8000/chat](ws://127.0.0.1:8000/chat).
- Check out [examples/websockets](https://github.com/patx/micropie/tree/main/examples/websockets) for a full chat example.
- Supports 3rd party libraries like Socket.IO. See [examples/socketio](https://github.com/patx/micropie/tree/main/examples/socketio).

### **4. Jinja2 Template Rendering**
Dynamic HTML generation is supported via Jinja2, rendered asynchronously using Python's `asyncio` library.

#### **`app.py`**
```python
class MyApp(App):
    async def index(self):
        return await self._render_template("index.html", title="Welcome", message="Hello from MicroPie!")
```

#### **`templates/index.html`**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
</head>
<body>
    <h1>{{ message }}</h1>
</body>
</html>
```

### **5. Static File Serving**
MicroPie does not natively serve static files to keep it lightweight. For static file serving, integrate libraries 
like **ServeStatic** or **Starlette’s StaticFiles** with Uvicorn. You can also easily implement this yourself using
`aiofiles`. Check out [examples/static_content](https://github.com/patx/micropie/tree/main/examples/static_content) for examples.

### **6. Streaming Responses**
Support for streaming responses makes it easy to send data in chunks.

```python
class MyApp(App):
    async def stream(self):
        async def generator():
            for i in range(1, 6):
                yield f"Chunk {i}\n"
        return generator()
```

### **7. Sessions and Cookies**
Built-in session handling simplifies state management:

```python
class MyApp(App):
    async def index(self):
        if "visits" not in self.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        return f"You have visited {self.request.session['visits']} times."
```

You can also use the `SessionBackend` class to create custom session backends. See [examples/sessions](https://github.com/patx/micropie/tree/main/examples/sessions).

### **8. Middleware**
MicroPie supports pluggable middleware to hook into the request lifecycle. Here's a trivial example using `HttpMiddleware`:

```python
from MicroPie import App, HttpMiddleware

class MiddlewareExample(HttpMiddleware):
    async def before_request(self, request):
        print("Hook before request")

    async def after_request(self, request, status_code, response_body, extra_headers):
        print("Hook after request")

class Root(App):
    async def index(self):
        return "Hello, World!"

app = Root()
app.middlewares.append(MiddlewareExample())
```

### **9. Deployment**
MicroPie apps can be deployed using any ASGI server. For example, using Uvicorn:
```bash
uvicorn app:app --workers 4 --port 8000
```

## **Learn by Examples**
The best way to see MicroPie in action is through the [examples folder](https://github.com/patx/micropie/tree/main/examples), which includes:
- Template rendering
- Custom HTTP request handling
- File uploads
- Serving static content with ServeStatic
- Session usage
- JSON requests and responses
- WebSocket-based chat application
- Async streaming
- Middleware
- Form handling and POST requests
- And more

## **Why ASGI?**
ASGI is the future of Python web development, offering:
- **Concurrency**: Handle thousands of simultaneous connections efficiently.
- **WebSockets**: Native WebSocket support in MicroPie for real-time communication.
- **Scalability**: Ideal for modern, high-traffic applications.

MicroPie leverages ASGI to provide a simple, flexible framework for both HTTP and WebSocket applications, maintaining the ease of use you're accustomed to with WSGI apps while giving you full control over your tech stack.

## **Comparisons**

### **Features vs Other Popular Frameworks**
| Feature             | MicroPie      | Flask        | CherryPy   | Bottle       | Django       | FastAPI         |
|---------------------|---------------|--------------|------------|--------------|--------------|-----------------|
| **Ease of Use**     | Very Easy     | Easy         | Easy       | Easy         | Moderate     | Moderate        |
| **Routing**         | Automatic     | Manual       | Manual     | Manual       | Views        | Manual          |
| **Template Engine** | Jinja2 (Opt.) | Jinja2       | None       | SimpleTpl    | Django       | Jinja2          |
| **Middleware**      | Yes           | Yes          | Yes        | Yes          | Yes          | Yes             |
| **Session Handling**| Simple        | Extension    | Built-in   | Plugin       | Built-in     | Extension       |
| **Async Support**   | Yes (ASGI)    | No (Quart)   | No         | No           | Limited      | Yes (ASGI)      |
| **WebSocket Support**| Yes          | No (Quart)   | Limited    | No           | Channels     | Yes             |
| **Built-in Server** | No            | No           | Yes        | Yes          | Yes          | No              |

## Benchmark Results

Below is a performance comparison of various ASGI frameworks using their "Hello World" examples from each framework's website. Ran with `uvicorn` with 4 workers and `wrk -t12 -c1000 -d30s http://127.0.0.1:8000/`:

| Framework       | Requests/sec | Transfer/sec | Avg Latency | Stdev Latency | Max Latency | Socket Errors (timeouts) |
|-----------------|--------------|--------------|-------------|---------------|-------------|--------------------------|
| **Muffin**      | 6508.80      | 0.90MB       | 132.62ms    | 69.71ms       | 2.00s       | 533                      |
| **Starlette**   | 6340.40      | 0.86MB       | 130.72ms    | 75.55ms       | 2.00s       | 621                      |
| **BlackSheep**  | 5928.99      | 0.98MB       | 142.48ms    | 73.61ms       | 1.99s       | 526                      |
| **MicroPie**    | 5447.04      | 0.85MB       | 157.04ms    | 71.55ms       | 2.00s       | 470                      |
| **Litestar**    | 5088.38      | 730.46KB     | 151.59ms    | 81.75ms       | 2.00s       | 662                      |
| **Sanic**       | 4236.29      | 682.61KB     | 196.80ms    | 80.56ms       | 2.00s       | 452                      |
| **FastAPI**     | 2352.53      | 326.23KB     | 396.95ms    | 112.41ms      | 2.00s       | 516                      |

## **Suggestions or Feedback?**
We welcome suggestions, bug reports, and pull requests!
- File issues or feature requests [here](https://github.com/patx/micropie/issues).
- Security issues that should not be public, email `harrisonerd [at] gmail.com`.

# **API Documentation**

## Session Backend Abstraction

MicroPie provides an abstraction for session backends, allowing you to define custom session storage mechanisms.

### `SessionBackend` Class

#### Methods

- `load(session_id: str) -> Dict[str, Any]`
  - Abstract method to load session data given a session ID.

- `save(session_id: str, data: Dict[str, Any], timeout: int) -> None`
  - Abstract method to save session data.

### `InMemorySessionBackend` Class

An in-memory implementation of the `SessionBackend`.

#### Methods

- `__init__()`
  - Initializes the in-memory session backend.

- `load(session_id: str) -> Dict[str, Any]`
  - Loads session data for the given session ID.

- `save(session_id: str, data: Dict[str, Any], timeout: int) -> None`
  - Saves session data for the given session ID.

## Middleware Abstraction

MicroPie allows you to create pluggable middleware to hook into the request lifecycle.

### `HttpMiddleware` Class

#### Methods

- `before_request(request: Request) -> None`
  - Abstract method called before the request is processed.

- `after_request(request: Request, status_code: int, response_body: Any, extra_headers: List[Tuple[str, str]]) -> None`
  - Abstract method called after the request is processed but before the final response is sent to the client.

## Request Object

### `Request` Class

Represents an HTTP request in the MicroPie framework.

#### Attributes

- `scope`: The ASGI scope dictionary for the request.
- `method`: The HTTP method of the request.
- `path_params`: List of path parameters.
- `query_params`: Dictionary of query parameters.
- `body_params`: Dictionary of body parameters.
- `get_json`: JSON request body object.
- `session`: Dictionary of session data.
- `files`: Dictionary of uploaded files.
- `headers`: Dictionary of headers.

## WebSocket Object

### `WebSocket` Class

Represents a WebSocket connection in the MicroPie framework.

#### Attributes

- `scope`: The ASGI scope dictionary for the WebSocket connection.
- `query_params`: Dictionary of query parameters.
- `headers`: Dictionary of headers.

#### Methods

- `accept() -> None`
  - Accepts the WebSocket connection.

- `send_text(data: str) -> None`
  - Sends text data over the WebSocket.

- `send_json(data: Any) -> None`
  - Sends JSON data over the WebSocket.

- `receive_text() -> str`
  - Receives text data from the WebSocket.

- `receive_json() -> Any`
  - Receives JSON data from the WebSocket.

- `close(code: int = 1000) -> None`
  - Closes the WebSocket connection with an optional status code.

## Application Base

### `App` Class

The main ASGI application class for handling HTTP and WebSocket requests in MicroPie.

#### Methods

- `__init__(session_backend: Optional[SessionBackend] = None) -> None`
  - Initializes the application with an optional session backend.

- `request -> Request`
  - Retrieves the current HTTP request from the context variable.

- `__call__(scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None`
  - ASGI callable interface for the server. Handles `http` and `websocket` scope types.

- `_asgi_app_http(scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None`
  - ASGI application entry point for handling HTTP requests.

- `_handle_websocket(scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None`
  - ASGI application entry point for handling WebSocket connections.

- `_parse_cookies(cookie_header: str) -> Dict[str, str]`
  - Parses the Cookie header and returns a dictionary of cookie names and values.

- `_parse_multipart(reader: asyncio.StreamReader, boundary: bytes)`
  - Parses multipart/form-data from the given reader using the specified boundary.
  - *Requires*: `multipart` and `aiofiles`

- `_send_response(send: Callable[[Dict[str, Any]], Awaitable[None]], status_code: int, body: Any, extra_headers: Optional[List[Tuple[str, str]]] = None) -> None`
  - Sends an HTTP response using the ASGI send callable.

- `_redirect(location: str) -> Tuple[int, str]`
  - Generates an HTTP redirect response.

- `_render_template(name: str, **kwargs: Any) -> str`
  - Renders a template asynchronously using Jinja2.
  - *Requires*: `jinja2`

The `App` class is the main entry point for creating MicroPie applications. It implements the ASGI interface and handles both HTTP and WebSocket requests.

## Response Formats

Handlers can return responses in the following formats for HTTP:

1. String or bytes or JSON
2. Tuple of (status_code, body)
3. Tuple of (status_code, body, headers)
4. Async or sync generator for streaming responses

For WebSocket handlers, use the `WebSocket` class methods to send/receive data.

## Error Handling

MicroPie provides built-in error handling for common HTTP status codes:

- `404 Not Found`: Automatically returned for non-existent HTTP routes.
- `400 Bad Request`: Returned for missing required parameters.
- `500 Internal Server Error`: Returned for unhandled exceptions.

For WebSockets, standard close codes (e.g., 1008 for policy violation, 1011 for internal errors) are used. Custom error handling can be implemented through middleware or WebSocket handler logic.

----

© 2025 Harrison Erd
