# MicroPie User Guides

Welcome to the comprehensive set of guides and examples designed to help you master the MicroPie framework. These guides and examples cover everything from getting started to advanced topics like deployment and security.

## **1. Beginner's Guide to MicroPie Framework**

### Introduction to MicroPie
MicroPie is a lightweight Python web framework designed for rapid development with minimal configuration. It provides essential features such as routing, templating, and session management.

### Creating Your First Application
1. Install MicroPie:
   ```bash
   pip install micropie
   ```
2. Create a `server.py` file with:
   ```python
   from MicroPie import Server

   class MyApp(Server):
       def index(self):
           return "Hello, MicroPie!"

   MyApp().run()
   ```
3. Run the server:
   ```bash
   python server.py
   ```
4. Visit `http://127.0.0.1:8080` to see your app in action.

### Understanding Routing
MicroPie automatically maps URL paths to class methods, making routing simple and intuitive.


## **2. MicroPie Templating with Jinja2**

### Creating Templates
MicroPie integrates with Jinja2 for dynamic HTML rendering. Store your templates in a `templates/` folder.

Example template (`index.html`):
```html
<!DOCTYPE html>
<html>
<body>
    <h1>Hello, {{ name }}!</h1>
</body>
</html>
```

### Rendering Templates
In your MicroPie application:
```python
return self.render_template("index.html", name="MicroPie User")
```


## **3. Session Management in MicroPie**

### How Sessions Work
MicroPie uses cookies to store session IDs, allowing persistent data across requests.

### Managing Session Data
```python
self.session['username'] = 'JohnDoe'
print(self.session.get('username'))
```

### Securing Sessions
- Use HTTPS for secure cookie transmission.
- Configure session timeout to prevent long-term exposure.


## **4. Advanced Database Handling with PickleDB**

### Storing Data
```python
from pickledb import PickleDB

db = PickleDB("data.db")
db.set("key", "value")
db.save()
```

### Querying Data
```python
value = db.get("key")
```

### Backup Strategies
- Regular backups of `data.db`.
- Automated scripts for periodic exports.


## **5. Security Best Practices for MicroPie Applications**

### Input Validation
Always validate user inputs to prevent injection attacks.

### Authentication
Implement secure authentication mechanisms using sessions and encryption.

### Secure Deployment
- Use HTTPS.
- Set secure headers.
- Perform regular security audits.


## **6. Extending MicroPie with REST APIs**

### Creating an API Endpoint
```python
class MyApp(Server):
    def api_greet(self, name):
        return {"message": f"Hello, {name}!"}
```

### Testing with cURL
```bash
curl http://127.0.0.1:8080/api_greet?name=Alice
```


## **7. Deploying MicroPie Applications on Cloud Platforms**

### AWS Deployment
- Use AWS Elastic Beanstalk for easy deployments.

### Google Cloud Run
Deploy using:
```bash
gcloud run deploy --source .
```


## **8. Logging and Monitoring MicroPie Applications**

### Setting Up Logging
```python
import logging
logging.basicConfig(level=logging.INFO)
logging.info("Server started")
```

### Using Monitoring Tools
Integrate with tools like Prometheus and Grafana.


## **9. Styling MicroPie Applications with CSS Frameworks**

### Integrating Bootstrap
Add the Bootstrap CDN link to your templates:
```html
<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css">
```

### Customizing Styles
Create a `static/` folder and include your CSS files.


## **10. Automated Testing for MicroPie Applications**

### Writing Unit Tests
```python
import unittest
from MicroPie import Server

class TestApp(unittest.TestCase):
    def test_index(self):
        app = MyApp()
        response = app.index()
        self.assertEqual(response, "Hello, MicroPie!")

if __name__ == "__main__":
    unittest.main()
```

### Using pytest
```bash
pytest test_app.py
```

# Main Examples
Check out the other directors `gunicorn`, `todo-app`, `pastebin-app`, and `websockets` for even more examples.

These guides aim to provide a thorough understanding of the MicroPie framework and its capabilities. Whether you're a beginner or an experienced developer, you'll find valuable insights and practical examples to enhance your web development skills.


