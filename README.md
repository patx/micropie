[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**

**MicroPie** is a lightweight Python web framework that makes building web applications simple and efficient. It includes features such as routing, session management, ASGI support, and Jinja2 template rendering.

### **Key Features**
*"Fast, efficient, and deliciously simple."*

- 🚀 **Easy Setup:** Minimal configuration required. Our setup is so simple, you’ll have time for dessert.
- 🔄 **Routing:** Class based routing. Maps URLs to functions automatically. So easy, even your grandma could do it (probably).
- 🔐 **Sessions:** Simple session management using cookies.
- 🎨 **Templates:** Jinja2 for dynamic HTML pages.
- ⚡ **Fast & Lightweight:** No unnecessary dependencies. Life’s too short for bloated frameworks.
- 🖥️ **ASGI support:** Deploy with any ASGI server, like **uvicorn** making web development easy as... pie!


## **Install**
To install MicroPie [from the PyPI](https://pypi.org/project/MicroPie/) run the following command:
```bash
pip install micropie
```
This will install MicroPie along with `jinja2` as a dependency, enabling the built-in `render_template` method. This is the recommended way to install this framework.

To run your application you need an ASGI web server, like **uvicorn**. Install it with:
```bash
pip install uvicorn
```
MicroPie will work with any ASGI server of your choice!


## **Getting Started**

Create a basic MicroPie app in `app.py`:

```python
from MicroPie import Server

class MyApp(Server):
    async def index(self, name="Guest"):
        return f"Hello, {name}!"

app = MyApp()
```

Run the server:

```bash
uvicorn app:app
```

Visit your app at [http://127.0.0.1:8000](http://127.0.0.1:8000). In MicroPie your application code can look just like the WSGI code you are used to writing!


## **Learn by Examples**
Check out the [examples folder](https://github.com/patx/micropie/tree/development/examples) for more advanced usage, including:
- Template rendering
- Custom HTTP request handling
- File uploads
- Session usage
- Websockets with Socket.io
- Async Streaming
- Form handling


## **Notes on WebSockets**
MicroPie does not handle WebSockets out of the box. While the underlying ASGI interface can theoretically handle WebSocket connections, MicroPie’s routing and request-handling logic is designed primarily for HTTP. If you need WebSocket functionality, you’ll need to either:

- Write or integrate your own custom ASGI WebSocket handler, or
- Use a dedicated library such as Socket.IO or channels with your ASGI server alongside MicroPie.

Check out [examples/socketio](https://github.com/patx/micropie/tree/development/examples/socketio) to see Socket.io integration.


## **Feature Comparison**

| Feature             | MicroPie  | Flask      | CherryPy  | Bottle     | Django            | FastAPI    |
|---------------------|-----------|------------|-----------|------------|-------------------|------------|
| **Ease of Use**     | Very Easy | Easy       | Easy      | Easy       | Moderate          | Moderate   |
| **Routing**         | Automatic | Manual     | Manual    | Manual     | Automatic         | Automatic  |
| **Template Engine** | Jinja2    | Jinja2     | None      | SimpleTpl  | Django Templating | Jinja2     |
| **Session Handling**| Built-in  | Extension  | Built-in  | Plugin     | Built-in          | Extension  |
| **Request Handling**| Simple    | Flexible   | Advanced  | Simple     | Advanced          | Advanced   |
| **Performance**     | High      | High       | Moderate  | High       | Moderate          | Very High  |
| **WSGI Support**    | No (ASGI) | Yes        | Yes       | Yes        | Yes               | No (ASGI)  |
| **Async Support**   | Yes       | No (Quart) | No        | No         | Limited           | Yes        |
| **Deployment**      | Simple    | Moderate   | Moderate  | Simple     | Complex           | Moderate   |
| **Built-in Server** | No        | No         | Yes       | Yes        | Yes               | No         |


## **Suggestions or Feedback?**
We welcome suggestions, bug reports, and pull requests!
- File issues or feature requests [here](https://github.com/patx/micropie/issues).

