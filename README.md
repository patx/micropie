# MicroPie: Welcome to Your Lightweight Python Web Framework

## **Why Choose This Server?**

🌟 **Effortless Setup**: Get your server running in seconds without bloated dependencies.

🌟 **Customizable**: Define your own routes, templates, and logic with ease.

🌟 **Session Management**: Built-in support for session tracking and management.

🌟 **Dynamic Content**: Render templates dynamically using Jinja2.

🌟 **Secure & Validated**: Automatic validation of request data to avoid common pitfalls.

🌟 **Perfect for Prototypes**: Quickly spin up a server for your next big idea.

---

## **Features**

### 🚀 Session Management
- Automatic creation and tracking of client sessions using cookies.
- Session timeout handling ensures data security and resource cleanup.

### 📄 Template Rendering
- Use Jinja2 to create dynamic and reusable HTML templates.

### 🌐 Dynamic Routing
- Route requests to specific methods dynamically based on the URL path.

### ✅ Input Validation
- Validate GET and POST data to ensure only well-formed requests are processed.

### 🔄 Redirect Support
- Easily redirect users to other URLs with the `redirect` method.

---

## **Getting Started**

### 1. **Install Dependencies**
Ensure you have Python 3.x installed. Install MicroPie from the PyPI:

```bash
pip install micropie
```

### 2. **Set Up Your Environment**
Create a directory structure:

```
project/
  |-- server.py   # Your server script
  |-- templates/  # Directory for your HTML templates
```

### 3. **Create an HTML Template**
Save the following as `templates/index.html`:

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
</body>
</html>
```

### 4. **Run the Server**
Create `server.py` with the following content:

```python
from server import Server

if __name__ == "__main__":
    server = Server()
    server.run()
```

Run the server:

```bash
python server.py
```

Visit your server at [http://127.0.0.1:8080](http://127.0.0.1:8080).

---

## **Simple Example**

Add a custom route handler:

```python
class Server:
    def index(self):
        return self.render_template("index.html", title="Home", message="Welcome to our server!")
```

Access this route at `/`.

---

## **Advanced Example**

### **Handling Forms and Sessions**
Add a login form to `templates/login.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
</head>
<body>
    <form method="POST" action="/login">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" required>
        <button type="submit">Login</button>
    </form>
</body>
</html>
```

Add a `login` route:

```python
class Server:
    def login(self):
        if self.request == "POST":
            username = self.body_params.get("username", [None])[0]
            if username:
                self.session["user"] = username
                return self.redirect("/welcome")
            else:
                return "<h1>Invalid Username</h1>"

    def welcome(self):
        user = self.session.get("user", "Guest")
        return f"<h1>Welcome, {user}!</h1>"
```

Access this flow:
1. Go to `/login`.
2. Submit a username.
3. Redirected to `/welcome`.

---

## **Powerful Customization**

- **Validation Hooks**: Add custom validation rules for GET/POST requests.
- **Middleware**: Extend the `_handle_request` method to add pre- or post-processing.
- **Error Pages**: Customize `404` and `500` responses directly in your server.

---

## **Why Developers Love It**

💡 **"Simple, yet powerful. This server became my go-to tool for quick prototypes."**

💡 **"With built-in session management and Jinja2 support, it covers 90% of my use cases out-of-the-box."**

💡 **"The validation and dynamic routing features saved me countless hours. Highly recommended!"**

---

## **Ready to Get Started?**

Download or clone the repository now and start building your next project with ease!

**🚀 Let’s code your ideas into reality!**
