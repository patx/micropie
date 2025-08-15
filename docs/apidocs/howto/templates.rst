Rendering templates
==================

MicroPie can render HTML templates using the Jinja2 template engine.
Templates allow you to separate presentation from code by placing
HTML in separate files.  Template rendering is optional; you can use
MicroPie without Jinja2 installed, but the
:meth:`~micropie.App._render_template` method will not be available.

Installing Jinja2
-----------------

If you installed MicroPie with the ``[standard]`` extra, Jinja2 is
already available.  Otherwise install it with pip:

.. code-block:: console

   $ pip install jinja2

Creating templates
------------------

MicroPie looks for templates in a directory called ``templates`` in
your current working directory.  Use normal Jinja2 syntax in your
templates.  Here is a simple ``templates/index.html`` file:

.. code-block:: html

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

Rendering a template
--------------------

To render a template, call :meth:`~micropie.App._render_template` from
within an asynchronous handler.  The method returns a string containing
the rendered HTML.  Because template loading and rendering may block,
MicroPie runs it in a background thread using ``asyncio.to_thread``.

.. code-block:: python

   from micropie import App

   class MyApp(App):
       async def index(self):
           return await self._render_template(
               "index.html",
               title="Welcome",
               message="Hello from MicroPie!",
           )

   app = MyApp()

When you visit ``/`` in your browser, MicroPie returns the rendered
HTML with a ``Content‑Type`` of ``text/html; charset=utf‑8``.

Template variables
------------------

You can pass arbitrary keyword arguments to `_render_template`.  These
become variables in the Jinja2 template.  For more information on
creating complex templates, including inheritance and control flow,
refer to the `Jinja2 documentation <https://jinja.palletsprojects.com>`_.