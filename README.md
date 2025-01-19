# MicroPie: An Actual Micro Web Framework

## **Welcome to MicroPie**

**MicroPie** is an ultra-lightweight Python web framework that gets out of your way, letting you build dynamic, fast, and scalable web apps with ease. With built-in Jinja2 templates, simple routing, and zero bloat, it’s the perfect choice for developers who value speed and simplicity.

Inspired by [CherryPy](http://redis.io/) and licensed under the BSD three-clause license, MicroPie delivers power and simplicity in one package.


## **Why MicroPie?**

🌟 **Effortless Setup**: Start building your app with just a few lines of code.

🌟 **Customizable**: Define routes, templates, and logic to suit your needs.

🌟 **Session Management**: Track and manage client sessions with ease.

🌟 **Dynamic Content**: Render reusable and dynamic HTML templates with Jinja2.

🌟 **Secure and Validated**: Protect your app with automatic request validation.

🌟 **Developer-Friendly**: Perfect for prototypes and lightweight applications.


## **Installation**

Install MicroPie easily with pip:

```bash
pip install micropie
```


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

Visit your app at [http://127.0.0.1:8080](http://127.0.0.1:8080). Add a query parameter like `?name=Alice` to see dynamic responses.


## **Features**

### **Dynamic Argument Mapping**
Handler methods now support direct mapping of query parameters to method arguments. Default values are honored, and missing required arguments will result in an error.

For `POST` requests, dynamic argument mapping also works by mapping keys from `body_params` into method arguments. This allows for seamless handling of form or JSON data in `POST` requests.

### **Using `query_params` or `body_params` Directly**
If you prefer, you can access parameters directly using the `query_params` or `body_params` dictionaries. This is useful for dynamic or unknown keys:

```python
class MyApp(Server):
    def greet(self):
        name = self.query_params.get("name", ["Guest"])[0]
        return f"Hello, {name}!"

    def submit(self):
        username = self.body_params.get("username", ["Anonymous"])[0]
        return f"Form submitted by: {username}"
```

You can combine both approaches for flexibility. For example:

```python
class MyApp(Server):
    def greet(self, age=30):
        # Use dynamic mapping for 'age' and query_params for others
        name = self.query_params.get("name", ["Guest"])[0]
        return f"Hello, {name}! You are {age} years old."

    def form_handler(self, token):
        # Use dynamic mapping for 'token' and body_params for others
        data = self.body_params.get("field", ["No data"])[0]
        return f"Token: {token}, Data: {data}"
```

- **Dynamic Mapping**: Ideal for well-defined parameters.
- **`query_params` and `body_params`**: Perfect for handling unexpected or dynamic inputs.

### **Query Parameters**
Query parameters are values passed in the URL after the `?` symbol. They are automatically parsed and mapped to method arguments if the argument names match the query parameter keys. For example:

```python
class MyApp(Server):
    def greet(self, name="Guest", age=0):
        return f"Hello, {name}! You are {age} years old."
```

- Access this at: `http://127.0.0.1:8080/greet?name=Alice&age=25`
- Default values are used if a parameter is not provided.

### **Body Parameters**
For `POST` requests, data sent in the request body is automatically parsed into the `body_params` dictionary and can also be dynamically mapped to method arguments:

```python
class MyApp(Server):
    def submit(self, username="Anonymous"):
        return f"Form submitted by: {username}"
```

Alternatively, access `body_params` directly for flexibility:

```python
class MyApp(Server):
    def submit(self):
        if self.request == 'POST':
            username = self.body_params.get('username', ['Anonymous'])[0]
            return f"Form submitted by: {username}"
        return '''<form method="POST">
                    <input name="username" placeholder="Enter your name" />
                    <button type="submit">Submit</button>
                  </form>'''
```

### **Template Rendering**
MicroPie integrates Jinja2 for dynamic and reusable templates. Create a file named `templates/index.html`:

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

Render the template in your app:

```python
class MyApp(Server):
    def index(self):
        return self.render_template("index.html", title="Welcome", message="Hello, MicroPie!")
```

### **Session Management**
Automatically track and manage user sessions with cookies:

```python
class MyApp(Server):
    def login(self):
        self.session['username'] = 'MicroPieUser'
        return 'Logged in!'

    def welcome(self):
        user = self.session.get('username', 'Guest')
        return f'Welcome, {user}!'
```


## **Examples**

### Handling Query Parameters

```python
class MyApp(Server):
    def greet(self, name="Guest"):
        return f'Hello, {name}!'
```

Access this at: `http://127.0.0.1:8080/greet?name=Alice`

### Handling Form Submissions

```python
class MyApp(Server):
    def form(self, field_name="Default Field"):
        return f'Received: {field_name}'
```

Alternatively:

```python
class MyApp(Server):
    def form(self):
        if self.request == 'POST':
            data = self.body_params.get('field_name', [''])[0]
            return f'Received: {data}'
        return '''<form method="POST">
                    <input name="field_name" />
                    <button type="submit">Submit</button>
                  </form>'''
```

### Redirecting Users

```python
class MyApp(Server):
    def redirect_example(self):
        return self.redirect("/new-location")

    def new_location(self):
        return 'You have been redirected.'
```


## **API Documentation**

### **Class: Server**

#### `run(host='127.0.0.1', port=8080)`
Starts the server on the specified host and port.

#### `render_template(template_name, **context)`
Renders a Jinja2 template with the given context.

- **Parameters:**
  - `template_name` (str): The name of the template file.
  - `**context` (dict): Key-value pairs to pass to the template.

#### `redirect(location)`
Redirects the client to a new location.

- **Parameters:**
  - `location` (str): The URL to redirect to.

#### `get_session(request_handler)`
Retrieves or creates a session for the current client.

- **Returns:**
  - dict: The session data.

#### `validate_request(method)`
Validates incoming request data for GET or POST methods.

- **Parameters:**
  - `method` (str): The HTTP method (GET or POST).

- **Returns:**
  - bool: Whether the request is valid.


## **Why Developers Love MicroPie**

💡 **"Simple, yet powerful. This framework became my go-to tool for quick prototypes."**

💡 **"With built-in session management and Jinja2 support, it covers most use cases out of the box."**

💡 **"The validation and routing features saved me hours of debugging."**


