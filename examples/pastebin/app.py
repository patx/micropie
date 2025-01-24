# -*- coding: utf-8 -*-
"""
    A simple no frills pastebin using MicroPie, pickleDB, and highlight.js.
"""

from uuid import uuid4

from MicroPie import Server
from pickledb import PickleDB
from markupsafe import escape


db = PickleDB('pastes.db')


class Root(Server):

    def index(self):
        if self.request == 'POST':
            paste_content = self.body_params.get('paste_content', [''])[0]
            pid = str(uuid4())
            db.set(pid, escape(paste_content))
            db.save()
            return self.redirect(f'/paste/{pid}')
        return self.render_template('index.html')

    def paste(self, paste_id, delete=None):
        if delete == 'delete':
            db.remove(paste_id)
            db.save()
            return self.redirect('/')
        return self.render_template('paste.html', paste_id=paste_id,
            paste_content=db.get(paste_id))


# Create a instance of our MicroPie App
app = Root()

# Run with `gunicorn app:wsgi_app`
wsgi_app = app.wsgi_app

# Run with `python3 app.py`
if __name__ == '__main__':
    app.run()
