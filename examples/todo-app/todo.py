# -*- coding: utf-8 -*-
"""
A ToDo Application using the MicroPie framework and KenobiDB.
"""

import os
from uuid import uuid4
from MicroPie import Server  # Import our MicroPie framework
from pickledb import PickleDB

# ------------------------------------------------------------------------------
# Database Setup
# ------------------------------------------------------------------------------
db = PickleDB("todo.db")

def add_item(content, tags):
    """Add an item to the database. Each document has content, tags, and an id."""
    item_id = str(uuid4())
    db.set(item_id, {"content": content, "tags": tags.split(), "id": item_id})
    db.save()

def matching_tags(tag):
    """Return all documents with a tag matching the specified arg in reverse order."""
    return [
        db.get(key) for key in db.all() if tag in db.get(key).get("tags", [])
    ][::-1]

def get_all_items():
    """Retrieve all documents in the database and return them in reverse order."""
    return [db.get(key) for key in db.all()][::-1]

def get_all_tags():
    """Return a list of every unique tag in the database."""
    tags = set()
    for key in db.all():
        tags.update(db.get(key).get("tags", []))
    return list(tags)

def delete_item(item_id):
    """Delete an item by its id."""
    db.remove(item_id)
    db.save()

# ------------------------------------------------------------------------------
# ToDoApp Class
# ------------------------------------------------------------------------------
class ToDoApp(Server):
    """Our ToDo application, based on the MicroPie Server."""

    users = {"username": "password"}  # Simple user store

    def login(self):
        """
        GET /login -> Display login form
        POST /login -> Authenticate user and set session
        """
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
        """GET /logout -> Clear session and redirect to login."""
        self.session.clear()
        return self.redirect("/login")

    def index(self):
        """
        GET / -> Displays all items and tags in index.html.
        Requires user to be logged in.
        """
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        return self.render_template(
            "index.html",
            seq=get_all_items(),
            tags=get_all_tags(),
            username=self.session.get("username"),
        )

    def add(self):
        """
        POST /add -> Add a new item, then redirect to /.
        Requires user to be logged in.
        """
        if not self.session.get("logged_in"):
            return self.redirect("/login")

        if self.request == "POST":
            add_item(
                self.body_params.get("content", [""])[0],
                self.body_params.get("tags", [""])[0],
            )
        return self.redirect("/")

    def delete(self, item_id):
        """
        GET /delete/<id> -> Delete an item by id and optionally redirect to a tag.
        Requires user to be logged in.
        """
        if not self.session.get("logged_in"):
            return self.redirect("/login")

        if item_id:
            delete_item(item_id)

        return self.redirect("/")

    def tag(self, tag_value):
        """
        GET /tag/<tag> -> Show items with that tag.
        Requires user to be logged in.
        """
        if not self.session.get("logged_in"):
            return self.redirect("/login")
        return self.render_template(
            "tag.html",
            tag=tag_value,
            tag_items=matching_tags(tag_value),
        )

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
app = ToDoApp()

if __name__ == "__main__"
    app.run()
else:
    wsgi_app = app.wsgi_app

