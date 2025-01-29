[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**

**MicroPie** is a lightweight, modern Python web framework that supports asynchronous web applications. Designed with flexibility and simplicity in mind, MicroPie enables you to handle high-concurrency HTTP applications with ease while allowing easy and natural integration with external tools like Socket.IO for real-time communication.

### **Key Features**
- 🔄 **Routing:** Automatic mapping of URLs to functions with support for dynamic and query parameters.
- 🔒 **Sessions:** Simple session management using cookies.
- 🎨 **Templates:** Jinja2, if installed, for rendering dynamic HTML pages.
- ✨ **ASGI-Powered:** Built w/ asynchronous support for modern web servers like Uvicorn and Daphne, enabling high concurrency.
- 🛠️ **Lightweight Design:** Minimal dependencies for faster development and deployment.
- ⚡ **Blazing Fast:** Check out how MicroPie compares to other popular ASGI frameworks below!

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
    async def submit_default_values(self, username="Anonymous"):
        return f"Form submitted by: {username}"

    async def submit_catch_all(self):
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
    async def index(self):
        if "visits" not in self.session:
            self.session["visits"] = 1
        else:
            self.session["visits"] += 1
        return f"You have visited {self.session['visits']} times."
```

### **8. Deployment**
MicroPie apps can be deployed using any ASGI server. For example, using Uvicorn if our application is saved as `app.py` and our `Server` subclass is assigned to the `app` variable we can run it with:
```bash
uvicorn app:app --workers 4 --port 8000
```


## **Learn by Examples**
The best way to get an idea of how MicroPie works is to see it in action! Check out the [examples folder](https://github.com/patx/micropie/tree/main/examples) for more advanced usage, including:
- Template rendering
- Custom HTTP request handling
- File uploads
- Serving static content with ServeStatic
- Session usage
- Websockets with Socket.io
- Async Streaming
- Form handling and POST requests
- And more

*Please note these are examples, showing the MicroPie API and routing, they are not meant for producton!*
## **Why ASGI?**
ASGI is the future of Python web development, offering:
- **Concurrency**: Handle thousands of simultaneous connections efficiently.
- **WebSockets**: Use tools like Socket.IO for real-time communication.
- **Scalability**: Ideal for modern, high-traffic applications.

MicroPie allows you to take full advantage of these benefits while maintaining simplicity and ease of use you're used to with your WSGI apps and it lets you choose what libraries you want to work with instead of forcing our ideas onto you!


## **Comparisons**

### **Features vs Other Popular Frameworks*
| Feature             | MicroPie      | Flask        | CherryPy   | Bottle       | Django       | FastAPI         |
|---------------------|---------------|--------------|------------|--------------|--------------|-----------------|
| **Ease of Use**     | Very Easy     | Easy         | Easy       | Easy         | Moderate     | Moderate        |
| **Routing**         | Automatic     | Manual       | Manual     | Manual       | Automatic    | Automatic       |
| **Template Engine** | Jinja2 (Opt.) | Jinja2       | None       | SimpleTpl    | Django Templating | Jinja2     |
| **Session Handling**| Simple        | Extension    | Built-in   | Plugin       | Built-in     | Extension       |
| **Async Support**   | Yes (ASGI)    | No (Quart)   | No         | No           | Limited      | Yes (ASGI)      |
| **Built-in Server** | No            | No           | Yes        | Yes          | Yes          | No              |

### **Performance vs Other ASGI Frameworks**
| Framework   |   Threads |   Connections |   Duration (s) |   Requests/sec |   Latency (ms) |   Transfer/sec (KB) |
|------------|----------:|--------------:|---------------:|---------------:|---------------:|--------------------:|
| FastAPI     |         4 |           100 |             30 |        1895.29 |          52.67 |              257.54 |
| MicroPie    |         4 |           100 |             30 |        2272.76 |          43.93 |              362.18 |
| Quart       |         4 |           100 |             30 |        1500.13 |          66.63 |              212.68 |
| Starlette   |         4 |           100 |             30 |        2305.50 |          43.30 |              326.88 |
| FastAPI     |         4 |           200 |             30 |        2015.90 |          99.78 |              273.94 |
| MicroPie    |         4 |           200 |             30 |        2516.01 |          79.31 |              400.92 |
| Quart       |         4 |           200 |             30 |        1574.15 |         126.63 |              223.16 |
| Starlette   |         4 |           200 |             30 |        2658.45 |          75.10 |              376.86 |
| FastAPI     |         4 |          1000 |             30 |        2129.72 |         463.63 |              289.44 |
| MicroPie    |         4 |          1000 |             30 |        2589.64 |         381.86 |              412.79 |
| Quart       |         4 |          1000 |             30 |        1557.83 |         628.80 |              221.01 |
| Starlette   |         4 |          1000 |             30 |        2887.07 |         342.99 |              409.37 |

*Tests were performed with `uvicorn` using 4 workers. Benchmarked with `wrk`. This a minimal baseline benchmark, and should be taken with a grain of salt.*

## **Suggestions or Feedback?**
We welcome suggestions, bug reports, and pull requests!
- File issues or feature requests [here](https://github.com/patx/micropie/issues).

