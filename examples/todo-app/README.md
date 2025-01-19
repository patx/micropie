# Guide: ToDo Application with MicroPie and PickleDB

This guide provides instructions on how to set up and run a simple ToDo web application using the **MicroPie** framework and **PickleDB** for data storage.

## **1. Overview**

The ToDo application allows users to:

- Log in and manage a session.
- Add, delete, and view ToDo items.
- Filter items by tags.

### **Technologies Used:**
- **MicroPie** – A lightweight Python web framework.
- **PickleDB** – A simple key-value database for storing tasks.
- **UUID** – For generating unique item identifiers.


## **2. Prerequisites**

Ensure Python and the required dependencies are installed:

```bash
pip install micropie pickledb
```


## **3. Application Code Explanation**

### **`todo.py` (Main Application)**

```python
import os
from uuid import uuid4
from MicroPie import Server
from pickledb import PickleDB

db = PickleDB("todo.db")

def add_item(content, tags):
    item_id = str(uuid4())
    db.set(item_id, {"content": content, "tags": tags.split(), "id": item_id})
    db.save()

def matching_tags(tag):
    return [
        db.get(key) for key in db.all() if tag in db.get(key).get("tags", [])
    ][::-1]

def get_all_items():
    return [db.get(key) for key in db.all()][::-1]

def get_all_tags():
    tags = set()
    for key in db.all():
        tags.update(db.get(key).get("tags", []))
    return list(tags)

def delete_item(item_id):
    db.remove(item_id)
    db.save()

class ToDoApp(Server):
    users = {"username": "password"}

    def login(self):
        if self.request == "GET":
            return self.render_template("login.html")
        if self.request == "POST":
            username = self.body_params.get("username", [""])[0]
            password = self.body_params.get("password", [""])[0]
            if self.users.get(username) == password:
                self.session.update({"logged_in": True, "username": username})
                return self.redirect("/")
            return self.render_template("login.html", error="Invalid credentials")

    def logout(self):
        self.session.clear()
        return self.redirect("/login")

    def index(self):
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        return self.render_template(
            "index.html",
            seq=get_all_items(),
            tags=get_all_tags(),
            username=self.session.get("username"),
        )

    def add(self):
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        if self.request == "POST":
            add_item(
                self.body_params.get("content", [""])[0],
                self.body_params.get("tags", [""])[0],
            )
        return self.redirect("/")

    def delete(self, item_id):
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        if item_id:
            delete_item(item_id)
        return self.redirect("/")

    def tag(self, tag_value):
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        return self.render_template(
            "tag.html",
            tag=tag_value,
            tag_items=matching_tags(tag_value),
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app = ToDoApp()
    app.run(host="0.0.0.0", port=port)
```

### **Explanation:**

1. **Database Operations (`PickleDB`)**
   - `add_item()` → Adds a new item to the database.
   - `get_all_items()` → Retrieves all stored items.
   - `delete_item()` → Removes an item by its ID.
   - `matching_tags()` → Finds items based on a given tag.
   - `get_all_tags()` → Retrieves unique tags from all items.

2. **Authentication System:**
   - Supports a simple username/password login.
   - Sessions are used to keep users logged in.

3. **Web Application (`MicroPie`)**
   - Routes:
     - `/` → Displays all ToDo items.
     - `/login` → User login page.
     - `/logout` → Ends the session.
     - `/add` → Adds a new ToDo item.
     - `/delete/<item_id>` → Deletes a specific item.
     - `/tag/<tag>` → Filters items by a tag.


## **4. Running the Application**

Start the application with:

```bash
python todo.py
```

Access the app at:

```
http://127.0.0.1:5000
```


## **5. Deployment with Gunicorn**

Run the application with Gunicorn for production:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 todo:ToDoApp
```


## **6. Deploying with Docker**

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY todo.py requirements.txt .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "todo.py"]
```

Build and run the container:

```bash
docker build -t micropie-todo .
docker run -p 5000:5000 micropie-todo
```


## **7. Conclusion**

This guide covers the setup and deployment of a ToDo application using MicroPie and PickleDB. It provides basic CRUD operations and authentication to manage tasks effectively.

For further improvements, consider integrating a more robust database and authentication system.


