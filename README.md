# MicroPie: A Minimalist Micro Web Framework

## **Introduction**

**MicroPie** is a lightweight Python web framework designed for simplicity and efficiency. It provides a minimal yet powerful toolkit to build dynamic web applications with ease. Featuring built-in support for routing, session management, and Jinja2 template rendering, MicroPie is an excellent choice for developers who want a straightforward and effective web framework.

## **Key Features**

- 🚀 **Effortless Setup:** Start building web applications with minimal configuration.
- 🔄 **Dynamic Routing:** Automatically maps URLs to function handlers.
- 🛡️ **Built-in Validation:** Validate incoming requests effortlessly.
- 🔐 **Session Management:** Track user sessions securely.
- 🎨 **Template Rendering:** Leverage Jinja2 for dynamic HTML generation.
- ⚡ **Lightweight & Fast:** Zero bloat, quick responses.

---

## **Installation**

Install MicroPie easily with pip:

```bash
pip install micropie
```

---

## **Getting Started**

### 1. Create Your First MicroPie App

Save the following code as `server.py`:

```python
from MicroPie import Server

class MyApp(Server):
    def index(self, name="Guest"):
        return f"Hello, {name}!"

MyApp().run()
```

Run the server:

```bash
python server.py
```

Visit your app at [http://127.0.0.1:8080](http://127.0.0.1:8080). Try adding `?name=Alice` to see dynamic responses.

---

## **Core Features Explained**

### **Routing**

MicroPie maps URL paths to methods in your server class:

```python
class MyApp(Server):
    def hello(self):
        return "Hello, world!"
```

Access this via: `http://127.0.0.1:8080/hello`

---

### **Handling Query Parameters**

Query parameters in URLs can be mapped directly to function arguments:

```python
class MyApp(Server):
    def greet(self, name="Guest"):
        return f"Hello, {name}!"
```

Access this via: `http://127.0.0.1:8080/greet?name=Alice`

---

### **Handling POST Requests**

Form data sent via POST requests is parsed and mapped to function arguments:

```python
class MyApp(Server):
    def submit(self, username="Anonymous"):
        return f"Form submitted by: {username}"
```

Alternatively, access raw body parameters:

```python
class MyApp(Server):
    def submit(self):
        username = self.body_params.get('username', ['Anonymous'])[0]
        return f"Submitted by: {username}"
```

---

### **Session Management**

MicroPie provides simple session handling:

```python
class MyApp(Server):
    def login(self):
        self.session['user'] = 'Alice'
        return "User logged in."

    def profile(self):
        user = self.session.get('user', 'Guest')
        return f"Welcome, {user}!"
```

Sessions are tracked using cookies and have a default expiration of 8 hours.

---

### **Template Rendering**

Use Jinja2 templates for dynamic HTML responses:

Create `templates/index.html`:

```html
<!DOCTYPE html>
<html>
<body>
    <h1>Hello, {{ name }}!</h1>
</body>
</html>
```

Render it in your app:

```python
class MyApp(Server):
    def index(self):
        return self.render_template("index.html", name="MicroPie")
```

---

### **Redirecting Users**

Redirect users to a different route easily:

```python
class MyApp(Server):
    def old_page(self):
        return self.redirect("/new-page")

    def new_page(self):
        return "Welcome to the new page!"
```

---

### **Request Validation**

MicroPie includes basic request validation:

```python
class MyApp(Server):
    def validate_request(self, method):
        if method == "GET" and "name" not in self.query_params:
            return False
        return True
```

---

## **Advanced Features**

### **Path Parameters**

Extract URL segments dynamically:

```python
class MyApp(Server):
    def user(self, user_id):
        return f"User ID: {user_id}"
```

Access via: `http://127.0.0.1:8080/user/123`

---

### **Cleanup Expired Sessions**

Sessions are automatically cleared after timeout:

```python
class MyApp(Server):
    def cleanup_sessions(self):
        super().cleanup_sessions()
```

---

## **API Documentation**

### **Class: `Server`**

#### `run(host='127.0.0.1', port=8080)`
Starts the server.

#### `render_template(template_name, **context)`
Renders an HTML template with provided data.

#### `redirect(location)`
Redirects the client to a new URL.

#### `get_session(request_handler)`
Retrieves or creates a session for the client.

#### `validate_request(method)`
Validates incoming GET/POST requests.

---

## **Examples**

### Handling Form Submissions

```python
class MyApp(Server):
    def submit(self):
        return '''<form method="POST">
                    <input name="username" />
                    <button type="submit">Submit</button>
                  </form>'''
```

### Custom 404 Handler

```python
class MyApp(Server):
    def not_found(self):
        return "Page not found!", 404
```

---

## **Why Choose MicroPie?**

- Ideal for quick prototyping and lightweight web services.
- No unnecessary dependencies.
- Intuitive and developer-friendly API.

---

## **License**

MicroPie is licensed under the BSD 3-Clause License.


