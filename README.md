[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## **Introduction**

**MicroPie** is a lightweight Python web framework that makes building web applications simple and efficient. It includes features such as routing, session management, ASGI support, and Jinja2 template rendering.

### **Key Features**
*"Fast, efficient, and deliciously simple."*

- 🚀 **Easy Setup:** Minimal configuration required. Our setup is so simple, you’ll have time for dessert.
- 🔄 **Routing:** Maps URLs to functions automatically. So easy, even your grandma could do it (probably).
- 🔐 **Sessions:** Simple session management using cookies.
- 🎨 **Templates:** Jinja2 for dynamic HTML pages.
- ⚡ **Fast & Lightweight:** No unnecessary dependencies. Life’s too short for bloated frameworks.
- 🖥️ **ASGI support:** Deploy with any ASGI server, like **uvicorn** making web development easy as... pie!

## **Installing MicroPie**
### **Normal Installation**
To install MicroPie [from the PyPI](https://pypi.org/project/MicroPie/) run the following command:
```bash
pip install micropie
```
This will install MicroPie along with `jinja2` as a dependency, enabling the built-in `render_template` method. This is the recommended way to install this framework.

To run your application you need an ASGI web server, like **uvicorn**. Install it with:
```bash
pip install uvicorn
```
MicroPie will also work with any ASGI server of your choice!

## **Getting Started**

Create a basic MicroPie app in `app.py`:

```python
from MicroPie import Server

class MyApp(Server):
    def index(self, name="Guest"):
        return f"Hello, {name}!"

app = MyApp()
```

Run the server:

```bash
uvicorn app:app
```

Visit your app at [http://127.0.0.1:8000](http://127.0.0.1:8000). In MicroPie your application code can look just like the WSGI code you are used to writing!

## **Core Features**

### **1. Routing**
Define methods to handle URLs:
```python
class MyApp(Server):
    def hello(self):
        return "Hello, world!"
```
Your methods can also, of course, be `async` whenever needed:
```python
class MyApp(Server):
    async def hello(self):
        return "Hello World!"
```

**Access:**
- Basic route: [http://127.0.0.1:8080/hello](http://127.0.0.1:8080/hello)

### **2. Handling GET Requests**

MicroPie allows passing data using query strings (`?key=value`) and URL path segments.

#### **Query Parameters**

You can pass query parameters via the URL, which will be automatically mapped to method arguments:

```python
class MyApp(Server):
    def greet(self, name="Guest"):
        return f"Hello, {name}!"
```

**Access:**
- Using query parameters: [http://127.0.0.1:8080/greet?name=Alice](http://127.0.0.1:8080/greet?name=Alice)
  - This will return: `Hello, Alice!`
- Using URL path segments: [http://127.0.0.1:8080/greet](http://127.0.0.1:8080/greet)
  - This will return: `Hello, Guest!`

#### **Path Parameters (Dynamic Routing)**

You can also pass parameters directly in the URL path instead of query strings:

```python
class MyApp(Server):
    def greet(self, name="Guest"):
        return f"Hello, {name}!"
```

**Access:**
- Using path parameters: [http://127.0.0.1:8080/greet/Alice](http://127.0.0.1:8080/greet/Alice)
  - This will return: `Hello, Alice!`
- Another example: [http://127.0.0.1:8080/greet/John](http://127.0.0.1:8080/greet/John)
  - This will return: `Hello, John!`

#### **Using Both Query and Path Parameters Together**

```python
class MyApp(Server):
    def profile(self, user_id):
        age = self.query_params.get('age', ['Unknown'])[0]
        return f"User ID: {user_id}, Age: {age}"
```

**Access:**
- [http://127.0.0.1:8080/profile/123?age=25](http://127.0.0.1:8080/profile/123?age=25)
  - Returns: `User ID: 123, Age: 25`
- [http://127.0.0.1:8080/profile/456](http://127.0.0.1:8080/profile/456)
  - Returns: `User ID: 456, Age: Unknown`

### **3. Handling POST Requests**

MicroPie supports handling form data submitted via HTTP POST requests. Form data is automatically mapped to method arguments.

#### **Handling Form Submission with Default Values**

```python
class MyApp(Server):
    def submit(self, username="Anonymous"):
        return f"Form submitted by: {username}"
```

#### **Accessing Raw POST Data**

```python
class MyApp(Server):
    def submit(self):
        username = self.body_params.get('username', ['Anonymous'])[0]
        return f"Submitted by: {username}"
```

#### **Handling Multiple POST Parameters**

```python
class MyApp(Server):
    def register(self):
        username = self.body_params.get('username', ['Guest'])[0]
        email = self.body_params.get('email', ['No Email'])[0]
        return f"Registered {username} with email {email}"
```

### **4. Handling Sessions**
MicroPie has built in session handling:
```python
class MyApp(Server):

    def index(self):
        # Initialize or increment visit count in session
        if 'visits' not in self.session:
            self.session['visits'] = 1
        else:
            self.session['visits'] += 1

        return f"Welcome! You have visited this page {self.session['visits']} times."

app = MyApp()  # Run with `uvicorn app:app` assuming this file saved as `app.py`
```

### **5. Jinja2 Built In**
MicroPie has Jinja template engine built in. You can use it with the `render_template` method. You can also implement any other template engine you would like.

#### **`app.py`**
Save the following as `app.py`:
```python
class MyApp(Server):
    def index(self):
        # Pass data to the template for rendering
        return self.render_template("index.html", title="Welcome", message="Hello from MicroPie!")

app = MyApp()  # Run with `uvicorn app:app`
```

#### **HTML**
In order to use the `render_template` method you must put your HTML template files in a directory at the same level as `app.py` titled `templates`. Save the following as `templates/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
</head>
<body>
    <h1>{{ message }}</h1>
    <p>This page is rendered using Jinja2 templates.</p>
</body>
</html>
```

### **6. Serving Static Files**
MicroPie can serve static files (such as CSS, JavaScript, and images) from a static directory using the built in `serve_static` method. To do this you must define a route you would like to serve your static files from. For example:
```python
class Root(Server):
    def static(self, filename):
        return self.serve_static(filename)
```

#### **Setup**
- Create a directory named `static` in the same location as your MicroPie application. For safety the `serve_static` method will only work if `filename` is in the `static` directory.
- Place your static files (e.g., style.css, script.js, logo.png) inside the static directory.

#### **Accessing Static Files**
Static files can be accessed via the `/static/` URL path. For example, if you have a file named `style.css` in the `static` directory, you can access it using:
```
http://127.0.0.1:8080/static/style.css
```

### **7. Streaming Responses**
MicroPie provides support for streaming responses, allowing you to send data to the client in chunks instead of all at once. This is particularly useful for scenarios where data is generated or processed over time, such as live feeds, large file downloads, or incremental data generation.

Check out the `streaming` folder in the `examples` to see MicroPie's streaming responses in action.


### **8. WebSockets**
MicroPie does not handle WebSockets out of the box. While the underlying ASGI interface can theoretically handle WebSocket connections, MicroPie’s routing and request-handling logic is designed primarily for HTTP. If you need WebSocket functionality, you’ll need to either:

- Write or integrate your own custom ASGI WebSocket handler, or
- Use a dedicated library such as Socket.IO or channels with your ASGI server alongside MicroPie.

Check out the `socketio` folder in the `examples` on this repo to see Socket.io integration.

## **API Reference**

### Class: Server

#### cleanup_sessions()
Removes expired sessions that have surpassed the timeout period.

#### redirect(location)
Returns a 302 redirect response to the specified URL.

#### render_template(name, **args)
Renders a Jinja2 template with provided context variables.

#### serve_static(filename)
Serve static files from the `static` directory.

## **Examples**
Check out the [examples folder](https://github.com/patx/micropie/tree/development/examples) for more advanced usage, including:
- Template rendering
- Custom HTTP request handling
- File uploads
- Session usage
- Websockets with Socket.io
- Async Streaming
- Form handling.

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

