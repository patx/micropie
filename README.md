[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**
**MicroPie** is a fast, lightweight, modern Python web (HTTP) framework built on ASGI for asynchronous web applications. Designed for **flexibility** and **simplicity**, it enables high-concurrency web apps with built-in session management, middleware, and optional template rendering. **Extensible** for integration with ASGI-compatible tools like [python-socketio](https://python-socketio.readthedocs.io/en/stable/server.html#running-as-an-asgi-application) and [ServeStatic](https://archmonger.github.io/ServeStatic/latest/quick-start/#using-with-asgi), it’s inspired by CherryPy and licensed under the BSD 3-Clause License.

### **Key Features**
- 🔄 **Routing:** Automatic mapping of URLs to functions with support for dynamic and query parameters.
- 🔒 **Sessions:** Simple, plugable, session management using cookies.
- 🎨 **Templates:** Jinja2, if installed, for rendering dynamic HTML pages.
- ⚙️ **Middleware:** Support for custom request middleware enabling functions like rate limiting, authentication, logging, and more.
- ✨ **ASGI-Powered:** Built w/ asynchronous support for modern web servers like Uvicorn, Hypercorn, and Daphne, enabling high concurrency.
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
Install MicroPie with **standard** optional dependencies via pip:
```bash
pip install micropie[standard]
```
This will install MicroPie along with `jinja2` for template rendering, and `multipart` for parsing multipart form data.

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

[MicroPie.py](https://raw.githubusercontent.com/patx/micropie/refs/heads/main/MicroPie.py)

Place it in your project directory, and you are good to go. Note that `jinja2` must be installed separately to use the `_render_template` method and/or `multipart` for handling file data (the `_parse_multipart` method), but this *is* optional and you can use MicroPie without them. To install the optional dependencies use:
```bash
pip install jinja2 multipart
```

By default MicroPie will use the `json` library from Python's standard library. If you need faster performance you can use `orjson`. MicroPie *will* use `orjson` *if installed* by default. If it is not installed, MicroPie will fallback to `json`. This means with or without `orjson` installed MicroPie will still handle JSON requests/responses the same. To install `orjson` and take advantage of it's performance, use:
```bash
pip install orjson
```

### **Install an ASGI Web Server**
In order to test and deploy your apps you will need a ASGI web server like Uvicorn, Hypercorn or Daphne. 

If you installed `micropie[all]` Uvicorn *should* be ready to use. If you didn't install all of MicroPie's optional dependencies, use:
```bash
pip install uvicorn
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
- **Custom Routing**: Use middleware for explicit routing (see [examples/middleware](https://github.com/patx/micropie/tree/main/examples/middleware) and [examples/rest](https://github.com/patx/micropie/tree/main/examples/rest)).
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

By default, MicroPie's route handlers can accept any request method, it's up to you how to handle any incoming requests! You can check the request method (and an number of other things specific to the current request state) in the handler with`self.request.method`. You can see how to handle POST JSON data at [examples/api](https://github.com/patx/micropie/tree/main/examples/api).

### **Real-Time Communication with Socket.IO**
Because of its designed simplicity, MicroPie does not handle WebSockets out of the box. While the underlying ASGI interface can theoretically handle WebSocket connections, MicroPie’s routing and request-handling logic is designed primarily for HTTP. While MicroPie does not natively support WebSockets (*yet!*), you can easily integrate dedicated Websockets libraries like **Socket.IO** alongside Uvicorn to handle real-time, bidirectional communication. Check out [examples/socketio](https://github.com/patx/micropie/tree/main/examples/socketio) to see this in action.


### **Jinja2 Template Rendering**
Dynamic HTML generation is supported via Jinja2. This happens asynchronously using Pythons `asyncio` library, so make sure to use the `async` and `await` with this method.

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
Here again, like Websockets, MicroPie does not have a built in static file method. While MicroPie does not natively support static files, if you need them, you can easily implement it in your application code or integrate dedicated libraries like **ServeStatic** or **Starlette’s StaticFiles** alongside Uvicorn to handle async static file serving. Check out [examples/static_content](https://github.com/patx/micropie/tree/main/examples/static_content) to see this in action.


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
MicroPie allows you to create plug-able middleware to hook into the request life cycle. Take a look a trivial example using `HttpMiddleware` to send the console messages before and after the request is processed. Check out [examples/middleware](https://github.com/patx/micropie/tree/main/examples/middleware) to see more.
```python
from MicroPie import App, HttpMiddleware

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

Middleware provides an easy and **reusable** way to extend the MicroPie framework. We can do things such as rate limiting, checking for max upload size in multipart requests, explicit routing, CSRF protection, and more.
### **Deployment**
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
- Middleware including, explicit routing
- Form handling and POST requests
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

## Benchmark Results

The table below summarizes the performance of various ASGI frameworks based on a 15-second `wrk` test with 4 threads and 64 connections, measuring a simple "hello world" JSON response. [Learn More](https://gist.github.com/patx/26ad4babd662105007a6e728f182e1db).

| Framework   | Total Requests | Req/Sec   | Transfer/Sec (MB/s) | Avg Latency (ms) | Stdev Latency (ms) | Max Latency (ms) |
|-------------|----------------|-----------|---------------------|------------------|--------------------|------------------|
| Blacksheep  | 831,432        | 55,060.05 | 7.98                | 1.15             | 0.39               | 15.11            |
| MicroPie    | 791,721        | 52,685.82 | 8.09                | 1.35             | 1.09               | 21.59            |
| Starlette   | 779,092        | 51,930.45 | 7.03                | 1.22             | 0.39               | 17.42            |
| Litestar    | 610,059        | 40,401.18 | 5.47                | 1.57             | 0.63               | 33.66            |
| FastAPI     | 281,493        | 18,756.73 | 2.54                | 3.52             | 1.82               | 56.73            |

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
- `files`: Dictionary of multipart data/streamed content.
- `headers`: Dictionary of headers.

## Application Base

### `App` Class

The main ASGI application class for handling HTTP requests in MicroPie.

#### Methods

- `__init__(session_backend: Optional[SessionBackend] = None) -> None`
  - Initializes the application with an optional session backend.

- `request -> Request`
  - Retrieves the current request from the context variable.

- `__call__(scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None`
  - ASGI callable interface for the server. Checks `scope` type.

- `_asgi_app_http(scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None`
  - ASGI application entry point for handling HTTP requests.

- `request(self) -> Request`
  - Accessor for the current request object. - Returns the current request from the context variable.

- `_parse_cookies(cookie_header: str) -> Dict[str, str]`
  - Parses the Cookie header and returns a dictionary of cookie names and values.

- `_parse_multipart(reader: asyncio.StreamReader, boundary: bytes) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]`
  - Asynchronously parses multipart/form-data from the given reader using the specified boundary. Returns a tuple of two dictionaries: `form_data` (text fields as key-value pairs) and `files` (file fields with metadata). Each file entry in `files` contains:
    - `filename`: The original filename of the uploaded file.
    - `content_type`: The MIME type of the file (defaults to `application/octet-stream`).
    - `content`: An `asyncio.Queue` containing chunks of file data as bytes, with a `None` sentinel signaling the end of the stream.
  - Handlers can consume the file data by iterating over the queue (e.g., using `await queue.get()`).
  - *Requires:* `multipart`
  
- `_send_response(send: Callable[[Dict[str, Any]], Awaitable[None]], status_code: int, body: Any, extra_headers: Optional[List[Tuple[str, str]]] = None) -> None`
  - Sends an HTTP response using the ASGI send callable.

- `_redirect(location: str) -> Tuple[int, str]`
  - Generates an HTTP redirect response.

- `_render_template(name: str, **kwargs: Any) -> str`
  - Renders a template asynchronously using Jinja2.
  - *Requires*: `jinja2`

The `App` class is the main entry point for creating MicroPie applications. It implements the ASGI interface and handles HTTP requests.

## Response Formats

Handlers can return responses in the following formats:

1. String or bytes or JSON
2. Tuple of (status_code, body)
3. Tuple of (status_code, body, headers)
4. Async or sync generator for streaming responses

## Error Handling

MicroPie provides built-in error handling for common HTTP status codes:

- `404 Not Found`: Automatically returned for non-existent routes
- `400 Bad Request`: Returned for missing required parameters
- `500 Internal Server Error`: Returned for unhandled exceptions

Custom error handling can be implemented through middleware.

----

© 2025 Harrison Erd
