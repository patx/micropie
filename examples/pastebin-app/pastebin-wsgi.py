"""
Example pastebin with added WSGI support. You can run it using gunicorn:

$ gunicorn pastebin-wsgi:wsgi_app
"""
from MicroPie import Server
from pickledb import PickleDB
from pygments import highlight
from pygments.lexers import guess_lexer
from pygments.formatters import HtmlFormatter
from uuid import uuid4

# Initialize the database
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
        return self.redirect(f"/paste/{pid}")

# Create the application instance
app = Root()

# Use the WSGI wrapper provided by MicroPie
wsgi_app = app.wsgi_app
