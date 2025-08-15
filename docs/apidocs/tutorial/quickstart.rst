Quick start
===========

This tutorial shows you how to install MicroPie and run a very simple
application.  By the end you will be able to serve an HTTP
endpoint that returns plain text.  This section assumes that you
already have Python 3.8 or later installed.

Installation
------------

MicroPie is distributed on the Python Package Index (PyPI).  The
recommended way to install it is via ``pip`` with the standard
optional dependencies:

.. code-block:: console

   $ pip install micropie[standard]

This command installs MicroPie along with the Jinja2 template engine
and the ``multipart`` parser for handling file uploads.  If you want
the fastest JSON parsing and a preconfigured ASGI server, you can
install all optional extras:

.. code-block:: console

   $ pip install micropie[all]

See :ref:`reference/session` for details about session back‑ends and
the :ref:`howto/templates` guide for information on templates.

Writing your first application
------------------------------

Create a file called ``app.py`` with the following contents:

.. code-block:: python

   from micropie import App

   class MyApp(App):
       async def index(self):
           return "Welcome to MicroPie ASGI."

   app = MyApp()

MicroPie applications are defined by subclassing :class:`~micropie.App`.
Each public method of your subclass becomes a potential route handler
automatically mapped to an HTTP path.  The special method ``index``
handles requests to the root path ``/``.  Handlers may be asynchronous
(``async def``) or synchronous functions and can return strings,
bytes, JSON‑serialisable objects, tuples of status and body, or an
async generator for streaming responses.

Running the application
-----------------------

MicroPie itself is not a web server; it is an ASGI application.  To
run it you will need an ASGI server such as Uvicorn, Hypercorn or
Daphne.  Install Uvicorn if you have not already:

.. code-block:: console

   $ pip install uvicorn

Start your application with Uvicorn:

.. code-block:: console

   $ uvicorn app:app

By default Uvicorn listens on ``http://127.0.0.1:8000``.  Open that URL
in your browser and you should see the text “Welcome to MicroPie ASGI.”

What’s next?
------------

Now that you have a running MicroPie application, proceed to the
:doc:`routing <routing>` tutorial to learn how URL paths map to
methods and how to pass parameters to your handlers.