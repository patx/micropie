# -*- coding: utf-8 -*-
"""
    A simple no frills pastebin using MicroPie, pickleDB, and pygments.
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
