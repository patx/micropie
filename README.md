[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

[![License](https://img.shields.io/github/license/patx/micropie)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/micropie)](https://pypi.org/project/micropie/)
[![PyPI Downloads](https://static.pepy.tech/badge/micropie)](https://pepy.tech/projects/micropie)

## **Introduction**
**MicroPie** is a fast, lightweight, modern Python web framework built on ASGI for asynchronous web applications. Designed for flexibility and simplicity, it enables high-concurrency web apps with built-in WebSockets, session management, middleware, lifecycle event handling, and optional template rendering. Extensible for integration with ASGI-compatible tools like [python-socketio](https://python-socketio.readthedocs.io/en/stable/server.html#running-as-an-asgi-application) and [ServeStatic](https://archmonger.github.io/ServeStatic/latest/quick-start/#using-with-asgi), it’s inspired by CherryPy and licensed under the BSD 3-Clause License.

### **Key Features**
- 📬 **Routing:** Automatic mapping of URLs to functions with support for dynamic and query parameters.
- 🔑 **Sessions:** Simple, pluggable session management using cookies.
- 🎨 **Templates:** Jinja2, if installed, for rendering dynamic HTML pages.
- 🚧 **Middleware:** Support for custom request middleware enabling functions like rate limiting, authentication, logging, and more.
- 💨 **Real-Time Communication:** Built-in WebSocket support for real-time, bidirectional communication.
- ☀️ **ASGI-Powered:** Built with asynchronous support for modern web servers like Uvicorn, Hypercorn, and Daphne, enabling high concurrency.
- ☁️ **Lightweight Design:** Only optional dependencies for flexibility and faster development/deployment.
- 👶 **Lifecycle Events:** ASGI lifespan event handling for startup and shutdown tasks (e.g., database initialization).
- 🏁 **Competitive Performance:** Check out how MicroPie compares to other popular ASGI frameworks below!

### **Useful Links**
- **Homepage**: [patx.github.io/micropie](https://patx.github.io/micropie)
- **Official Documentation**: [micropie.readthedocs.io](https://micropie.readthedocs.io/)
- **PyPI Page**: [pypi.org/project/MicroPie](https://pypi.org/project/MicroPie/)
- **GitHub Project**: [github.com/patx/micropie](https://github.com/patx/micropie)
- **File Issue/Request**: [github.com/patx/micropie/issues](https://github.com/patx/micropie/issues)
- **Example Applications**: [github.com/patx/micropie/tree/main/examples](https://github.com/patx/micropie/tree/main/examples)
- **Introduction Lightning Talk**: [Introduction to MicroPie on YouTube](https://www.youtube.com/watch?v=BzkscTLy1So)

### Latest Release Notes
View the latest release notes [here](https://github.com/patx/micropie/blob/main/docs/release_notes.md). It is useful to check release notes each time a new version of MicroPie is published. Any breaking changes (rare, but do happen) also appear here.

## **Installing MicroPie**

### **Installation**
Install MicroPie with **standard** optional dependencies via pip:
```bash
pip install micropie[standard]
```
This will install MicroPie along with `jinja2` for template rendering and `multipart` for parsing multipart form data.

If you would like to install **all** optional dependencies (everything from `standard` plus `orjson` and `uvicorn`) you can run:
```bash
pip install micropie[all]
```

### **Minimal Setup**
You can also install MicroPie without ANY dependencies via pip:
```bash
pip install micropie
```
For an ultra-minimalistic approach, download the standalone script (development version):

[micropie.py](https://raw.githubusercontent.com/patx/micropie/refs/heads/main/micropie.py)

Place it in your project directory, and you are good to go. Note that `jinja2` must be installed separately to use the `_render_template` method and/or `multipart` for handling file data (the `_parse_multipart` method), but this *is* optional and you can use MicroPie without them. To install the optional dependencies use:
```bash
pip install jinja2 multipart
```

By default MicroPie will use the `json` library from Python's standard library. If you need faster performance you can use `orjson`. MicroPie *will* use `orjson` *if installed* by default. If it is not installed, MicroPie will fallback to `json`. This means with or without `orjson` installed MicroPie will still handle JSON requests/responses the same. To install `orjson` and take advantage of its performance, use:
```bash
pip install orjson
```

### **Install an ASGI Web Server**
In order to test and deploy your apps you will need an ASGI web server like Uvicorn, Hypercorn, or Daphne.

If you installed `micropie[all]` Uvicorn *should* be ready to use. If you didn't install all of MicroPie's optional dependencies, use:
```bash
pip install uvicorn
```

## **Getting Started**

### **Create Your First ASGI App**

Save the following as `app.py`:
```python
from micropie import App

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

### **Route Handlers**

MicroPie's route handlers map URLs to methods in your `App` subclass, handling HTTP requests with flexible parameter mapping and response formats.

#### **Key Points**
- **Automatic Mapping**: URLs map to method names (e.g., `/greet` → `greet`, `/` → `index`).
- **Private Methods**: Methods starting with `_` (e.g., `_private_method`) are private and inaccessible via URLs, returning 404. **Security Note**: Use `_` for sensitive methods to prevent external access.
- **Parameters**: Automatically populated from:
  - Path segments (e.g., `/greet/Alice` → `name="Alice"`).
  - Query strings (e.g., `?name=Alice`).
  - Form data (POST/PUT/PATCH).
  - Session data (`self.request.session`).
  - File uploads (`self.request.files`).
  - Default values in method signatures.
- **HTTP Methods**: Handlers support all methods (GET, POST, etc.). Check `self.request.method` to handle specific methods.
- **Responses**:
  - String, bytes, or JSON-serializable object.
  - Tuple: `(status_code, body)` or `(status_code, body, headers)`.
  - Sync/async generator for streaming.

#### **Advanced Usage**
- **Custom Routing**: Use middleware for explicit routing (see [examples/middleware](https://github.com/patx/micropie/tree/main/examples/middleware) and [examples/explicit_routing](https://github.com/patx/micropie/tree/main/examples/explicit_routing)).
- **Errors**: Auto-handled 404/400; customize via middleware.
- **Dynamic Params**: Use `*args` for multiple path parameters.

#### **Flexible HTTP Routing for GET Requests**
MicroPie automatically maps URLs to methods within your `App` class. Routes can be defined as either synchronous or asynchronous functions, offering good flexibility.

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

#### **Flexible HTTP POST Request Handling**
MicroPie also supports handling form data submitted via HTTP POST requests. Form data is automatically mapped to method arguments. It is able to handle default values and raw/JSON POST data:
```python
class MyApp(App):
    async def submit_default_values(self, username="Anonymous"):
        return f"Form submitted by: {username}"

    async def submit_catch_all(self):
        username = self.request.body_params.get("username", ["Anonymous"])[0]
        return f"Submitted by: {username}"
```

By default, MicroPie's route handlers can accept any request method, it's up to you how to handle any incoming requests! You can check the request method (and a number of other things specific to the current request state) in the handler with `self.request.method`. You can see how to handle POST JSON data at [examples/json_api](https://github.com/patx/micropie/tree/main/examples/json_api).

### **Lifecycle Event Handling**
MicroPie supports ASGI lifespan events, allowing you to register asynchronous handlers for application startup and shutdown. This is useful for tasks like initializing database connections or cleaning up resources.

#### **Key Points**
- **Startup Handlers**: Register async handlers to run during `lifespan.startup` using `app.startup_handlers.append(handler)`.
- **Shutdown Handlers**: Register async handlers to run during `lifespan.shutdown` using `app.shutdown_handlers.append(handler)`.
- **Error Handling**: Errors during startup or shutdown are caught and reported via `lifespan.startup.failed` or `lifespan.shutdown.failed` events.
- **Use Cases**: Ideal for setting up database pools, external service connections, or logging systems on startup, and closing them on shutdown.

#### **Example**
```python
from micropie import App

async def setup_db():
    print("Setting up database...")
    # DB init code here
    print("Database setup complete!")

async def close_db():
    print("Closing database...")
    # DB close code here
    print("Database closed!")

class MyApp(App):
    async def index(self):
        return "Welcome to MicroPie ASGI."

app = MyApp()
app.startup_handlers.append(setup_db)
app.shutdown_handlers.append(close_db)
```
On startup, the `setup_db` method initializes the database connection. On shutdown (e.g., Ctrl+C), the `close_db` method closes it.

### Real-Time Communication with WebSockets and Socket.IO
MicroPie includes built-in support for WebSocket connections. WebSocket routes are defined in your App subclass using methods prefixed with `ws_`, mirroring the simplicity of MicroPie's HTTP routing. For example, a method named `ws_chat` handles WebSocket connections at `ws://<host>/chat`.

#### MicroPie’s WebSocket support allows you to:
- Define WebSocket handlers with the same intuitive automatic routing as HTTP (e.g., `/chat` maps to `ws_chat` method).
- Access query parameters, path parameters, and session data in WebSocket handlers, consistent with HTTP requests.
- Manage WebSocket connections using the WebSocket class, which provides methods like `accept`, `receive_text`, `send_text`, and `close`.

Check out a basic example:
```python
from micropie import App

class Root(App):
    async def ws_echo(self, ws):
        await ws.accept()
        while True:
            msg = await ws.receive_text()
            await ws.send_text(f"Echo: {msg}")

app = Root()
```

#### Use Socket.IO for Advanced Real-Time Features
If you want more advanced real-time features like automatic reconnection, broadcasting, or fallbacks (e.g., polling), you can integrate Socket.IO with your MicroPie app using Uvicorn as the server. See [examples/socketio](https://github.com/patx/micropie/tree/main/examples/socketio) for integration instructions and examples.

### **Jinja2 Template Rendering**
Dynamic HTML generation is supported via Jinja2. This happens asynchronously using Python's `asyncio` library, so make sure to use `async` and `await` with this method.

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

### **Static File Serving**
MicroPie does not natively support static files, if you need them, you can easily implement it in your application code or integrate dedicated libraries like **ServeStatic** or **Starlette’s StaticFiles** alongside Uvicorn to handle async static file serving. Check out [examples/static_content](https://github.com/patx/micropie/tree/main/examples/static_content) to see this in action.

### **Streaming Responses**
Support for streaming responses makes it easy to send data in chunks.

```python
class MyApp(App):
    async def stream(self):
        async def generator():
            for i in range(1, 6):
                yield f"Chunk {i}\n"
        return generator()
```

### **Sessions and Cookies**
Built-in session handling simplifies state management:

```python
class MyApp(App):
    async def index(self):
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        return f"You have visited {self.request.session['visits']} times."
```

You also can use the `SessionBackend` class to create your own session backend. You can see an example of this in [examples/sessions](https://github.com/patx/micropie/tree/main/examples/sessions).

### **Middleware**
MicroPie allows you to create pluggable middleware to hook into the request lifecycle. Take a look at a trivial example using `HttpMiddleware` to send console messages before and after the request is processed. Check out [examples/middleware](https://github.com/patx/micropie/tree/main/examples/middleware) to see more.
```python
from micropie import App, HttpMiddleware

class MiddlewareExample(HttpMiddleware):
    async def before_request(self, request):
        print("Hook before request")

    async def after_request(self, request, status_code, response_body, extra_headers):
        print("Hook after request")

class Root(App):
    async def index(self):
        print("Hello, World!")
        return "Hello, World!"

app = Root()
app.middlewares.append(MiddlewareExample())
```

Middleware provides an easy and **reusable** way to extend the MicroPie framework. We can do things such as rate limiting, checking for max upload size in multipart requests, **explicit routing**, CSRF protection, and more.

MicroPie apps can be deployed using any ASGI server. For example, using Uvicorn if our application is saved as `app.py` and our `App` subclass is assigned to the `app` variable we can run it with:
```bash
uvicorn app:app --workers 4 --port 8000
```

## **Learn by Examples**
The best way to get an idea of how MicroPie works is to see it in action! Check out the [examples folder](https://github.com/patx/micropie/tree/main/examples) for more advanced usage, including:
- Template rendering
- Custom HTTP request handling
- File uploads
- Serving static content
- Session usage
- JSON Requests and Responses
- Socket.io Integration
- Async Streaming
- Middleware including explicit routing and more
- Form handling and POST requests
- WebSockets
- Lifecycle event handling
- And more

## **Comparisons**

### **Features vs Other Popular Frameworks**
| Feature             | MicroPie      | Flask        | CherryPy   | Bottle       | Django       | FastAPI         |
|---------------------|---------------|--------------|------------|--------------|--------------|-----------------|
| **Routing**         | Automatic     | Manual       | Automatic  | Manual       | Views        | Manual          |
| **Template Engine** | Jinja2 (Opt.) | Jinja2       | Plugin     | SimpleTpl    | Django       | Jinja2          |
| **Middleware**      | Yes           | Yes          | Yes        | Yes          | Yes          | Yes             |
| **Session Handling**| Plugin        | Plugin       | Built-in   | Plugin       | Built-in     | Plugin          |
| **Async Support**   | Yes           | No           | No         | No           | Yes          | Yes             |
| **Built-in Server** | No            | No           | Yes        | Yes          | Yes          | No              |
| **Lifecycle Events**| Yes           | No           | Yes        | No           | Yes          | Yes             |

## Benchmark Results

The table below summarizes the performance of various ASGI frameworks based on a 15-second `wrk` test with 4 threads and 64 connections, measuring a simple "hello world" JSON response. [Learn More](https://gist.github.com/patx/39e846ed66bead3e42270ff193db35f8).

| Framework  | Requests/sec | Avg Latency (ms) | Max Latency (ms) | Transfer/sec (MB) | Total Requests | Data Read (MB) |
|------------|--------------|------------------|------------------|-------------------|----------------|----------------|
| Starlette  | 21615.41     | 3.00             | 90.34            | 2.93              | 324374         | 43.93          |
| MicroPie   | 18519.02     | 3.53             | 105.00           | 2.84              | 277960         | 42.68          |
| FastAPI    | 8899.40      | 7.22             | 56.09            | 1.21              | 133542         | 18.08          |
| Quart      | 8601.40      | 7.52             | 117.99           | 1.17              | 129089         | 17.60          |

## **Suggestions or Feedback?**
We welcome suggestions, bug reports, and pull requests!
- File issues or feature requests [here](https://github.com/patx/micropie/issues).
- Security issues that should not be public, email `harrisonerd [at] gmail.com`.

© 2025 Harrison Erd
