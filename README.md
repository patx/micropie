[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**

**MicroPie** is a lightweight, modern Python web framework that supports asynchronous web applications. Designed with flexibility and simplicity in mind, MicroPie enables you to handle high-concurrency HTTP applications with ease while allowing easy and natural integration with external tools like Socket.IO for real-time communication.

### **Key Features**
- 🚀 **Async & Sync Support:** Define routes as asynchronous or synchronous functions to suit your application's needs.
- 🔄 **Routing:** Automatic mapping of URLs to functions with support for dynamic and query parameters.
- 🔒 **Sessions:** Simple session management using cookies.
- 🎨 **Templates:** Jinja2, if installed, for rendering dynamic HTML pages.
- ✨ **ASGI-Powered:** Built for modern web servers like Uvicorn and Daphne, enabling high concurrency.
- 🛠️ **Lightweight Design:** Minimal dependencies for faster development and deployment.

## **Installing MicroPie**

### **Installation**
Install MicroPie via pip:
```bash
pip install micropie
```
This will install MicroPie along with `jinja2` for template rendering. Jinja2 is optional but recommended for using the `render_template` method.

### **Minimal Setup**
For an ultra-minimalistic approach, download the standalone script:

[MicroPie.py](https://raw.githubusercontent.com/patx/micropie/refs/heads/main/MicroPie.py)

Place it in your project directory, and you are good to go. Note that Jinja2 must be installed separately to use templates, but this *is* optional:
```bash
pip install jinja2
```

### **Install an ASGI Web Server**
In order to test and deploy your apps you will need a ASGI web server like uvicorn or Daphne. Install uvicorn with:
```bash
pip install uvicorn
```

## **Getting Started**

### **Create Your First ASGI App**

Save the following as `app.py`:
```python
from MicroPie import Server

class MyApp(Server):
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
MicroPie automatically maps URLs to methods within your `Server` class. Routes can be defined as either synchronous or asynchronous functions, offering good flexibility.

For GET requests, pass data through query strings or URL path segments, automatically mapped to method arguments.
```python
class MyApp(Server):
    def async greet(self, name="Guest"):
        return f"Hello, {name}!"
```
**Access:**
- [http://127.0.0.1:8000/greet?name=Alice](http://127.0.0.1:8000/greet?name=Alice) returns `Hello, Alice!`
- [http://127.0.0.1:8000/greet/Alice](http://127.0.0.1:8000/greet/Alice) returns `Hello, Alice!`

### **2. Flexible HTTP POST Request Handling**
MicroPie also supports handling form data submitted via HTTP POST requests. Form data is automatically mapped to method arguments. It is able to handle default values and raw POST data:
```python
class MyApp(Server):
    def submit_default_values(self, username="Anonymous"):
        return f"Form submitted by: {username}"

    def submit_catch_all(self):
        username = self.body_params.get('username', ['Anonymous'])[0]
        return f"Submitted by: {username}"
```


### **3. Real-Time Communication with Socket.IO**
Because of its designed simplicity, MicroPie does not handle WebSockets out of the box. While the underlying ASGI interface can theoretically handle WebSocket connections, MicroPie’s routing and request-handling logic is designed primarily for HTTP. While MicroPie does not natively support WebSockets, you can easily integrate dedicated Websockets libraries like **Socket.IO** alongside Uvicorn to handle real-time, bidirectional communication. Check out [examples/socketio](https://github.com/patx/micropie/tree/main/examples/socketio) to see this in action.


### **4. Jinja2 Template Rendering**
Dynamic HTML generation is supported via Jinja2. This happens asynchronously using Pythons `asyncio` library, so make sure to use the `async` and `await` with this method.

#### **`app.py`**
```python
class MyApp(Server):
    async def index(self):
        return await self.render_template("index.html", title="Welcome", message="Hello from MicroPie!")
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
Here again, like Websockets, MiroPie does not have a built in static file method. While MicroPie does not natively support static files, if you need them, you can easily integrate dedicated libraries like **ServeStatic** or **Starlette’s StaticFiles** alongside Uvicorn to handle async static file serving. Check out [examples/serve_static](https://github.com/patx/micropie/tree/main/examples/serve_static) to see this in action.


### **6. Streaming Responses**
Support for streaming responses makes it easy to send data in chunks.

```python
class MyApp(Server):
    async def stream(self):
        async def generator():
            for i in range(1, 6):
                yield f"Chunk {i}\n"
        return generator()
```

### **7. Sessions and Cookies**
Built-in session handling simplifies state management:

```python
class MyApp(Server):
    def index(self):
        if "visits" not in self.session:
            self.session["visits"] = 1
        else:
            self.session["visits"] += 1
        return f"You have visited {self.session['visits']} times."
```

### **8. Deployment**
MicroPie ASGI apps can be deployed using any ASGI server. For example, using Uvicorn:
```bash
uvicorn app:MyApp --workers 4 --port 8000
```


## **Learn by Examples**
Check out the [examples folder](https://github.com/patx/micropie/tree/main/examples) for more advanced usage, including:
- Template rendering
- Custom HTTP request handling
- File uploads
- Serving static content with ServeStatic
- Session usage
- Websockets with Socket.io
- Async Streaming
- Form handling


## **Why ASGI?**
ASGI is the future of Python web development, offering:
- **Concurrency**: Handle thousands of simultaneous connections efficiently.
- **WebSockets**: Use tools like Socket.IO for real-time communication.
- **Scalability**: Ideal for modern, high-traffic applications.

MicroPie allows you to take full advantage of these benefits while maintaining simplicity and ease of use you're used to with your WSGI apps.


## **Feature Comparison**

| Feature             | MicroPie      | Flask        | CherryPy   | Bottle       | Django       | FastAPI         |
|---------------------|---------------|--------------|------------|--------------|--------------|-----------------|
| **Ease of Use**     | Very Easy     | Easy         | Easy       | Easy         | Moderate     | Moderate        |
| **Routing**         | Automatic     | Manual       | Manual     | Manual       | Automatic    | Automatic       |
| **Template Engine** | Jinja2 (Opt.) | Jinja2       | None       | SimpleTpl    | Django Templating | Jinja2     |
| **Session Handling**| Simple        | Extension    | Built-in   | Plugin       | Built-in     | Extension       |
| **Async Support**   | Yes           | No (Quart)   | No         | No           | Limited      | Yes             |
| **Performance**     | Very High     | High         | Moderate   | High         | Moderate     | Extremely High  |
| **Built-in Server** | No            | No           | Yes        | Yes          | Yes          | No              |



## **Suggestions or Feedback?**
We welcome suggestions, bug reports, and pull requests!
- File issues or feature requests [here](https://github.com/patx/micropie/issues).

