# Guide: Building a Simple Pastebin with MicroPie, PickleDB, and Pygments

This guide provides instructions on how to set up and run a simple pastebin web application using the MicroPie framework, PickleDB for storage, and Pygments for syntax highlighting.


## **1. Overview**

This application allows users to:

- Submit code snippets to be stored.
- Retrieve and view formatted code with syntax highlighting.

### **Technologies Used:**
- **MicroPie** – A lightweight web framework.
- **PickleDB** – A lightweight key-value store for storing pastes.
- **Pygments** – A syntax highlighter for rendering code.


## **2. Prerequisites**

Ensure you have Python installed along with the required dependencies:

```bash
pip install micropie pickledb pygments
```


## **3. Application Code Explanation**

### **`pastebin.py` (Main Application)**

```python
"""
    A simple no frills pastebin using MicroPie, PickleDB, and Pygments.
"""

import os
from uuid import uuid4

from MicroPie import Server
from pickledb import PickleDB
from pygments import highlight
from pygments.lexers import guess_lexer
from pygments.formatters import HtmlFormatter


db = PickleDB("pastes.db")

def get_paste(pid, line_numbers=None):
    code = db.get(pid)
    return highlight(code, guess_lexer(code), HtmlFormatter())

class Root(Server):

    def index(self):
        return self.render_template("index.html")

    def paste(self, paste_id):
        return self.render_template("paste.html", paste_id=paste_id,
            paste_content=get_paste(paste_id))

    def add(self, paste_content):
        pid = str(uuid4())
        db.set(pid, paste_content)
        db.save()
        return self.redirect("/paste/{0}".format(pid))

Root().run()
```

### **Explanation:**

1. **Database Handling (`PickleDB`)**
   - Stores pastes using a simple key-value format.
   - `db.set(pid, paste_content)` saves new code snippets.
   - `db.get(pid)` retrieves stored snippets.

2. **Syntax Highlighting (`Pygments`)**
   - `highlight()` applies syntax highlighting to the pasted code.
   - `guess_lexer()` detects the programming language automatically.
   - `HtmlFormatter()` generates HTML-formatted output.

3. **Web Application (`MicroPie`)**
   - **Routes:**
     - `/` → Displays the home page.
     - `/paste/<paste_id>` → Shows highlighted paste content.
     - `/add` → Accepts new pastes and stores them.


## **4. Running the Application**

Start the pastebin server with:

```bash
python pastebin.py
```

Once running, access the application at:

```
http://127.0.0.1:8080
```


## **5. Testing the Application**

1. Open the home page and submit a new code snippet.
2. Copy the URL of the resulting paste and view the formatted output.


## **6. Deployment with Gunicorn**

For better performance in production environments, run the application using Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:8080 pastebin:Root
```


## **7. Deploying with Docker**

Create a `Dockerfile` to containerize the application:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY pastebin.py requirements.txt .
RUN pip install -r requirements.txt
EXPOSE 8080
CMD ["python", "pastebin.py"]
```

Build and run the container:

```bash
docker build -t micropie-pastebin .
docker run -p 8080:8080 micropie-pastebin
```


## **8. Improving the Application**

To enhance the functionality, consider:

- Adding **expiration policies** for pastes.
- Implementing **user authentication**.
- Using a more robust database such as SQLite or PostgreSQL.
- Adding a REST API for programmatic access.


## **9. Conclusion**

This guide covered the setup and deployment of a simple pastebin web application using MicroPie, PickleDB, and Pygments. This setup is ideal for quick, lightweight code sharing with syntax highlighting.

For further questions or improvements, feel free to contribute to the project or explore additional features.


