Serving static files
====================

MicroPie deliberately avoids bundling a static file server.  Serving
static content such as images, CSS and JavaScript can be delegated to
a specialised middleware or a separate web server.  This approach
keeps the core framework small and flexible.

Using a static file middleware
------------------------------

To serve static files from within your MicroPie application, you can
use third‑party libraries such as
`ServeStatic <https://archmonger.github.io/ServeStatic/latest/>`_ or
Starlette’s `StaticFiles` class.  The example below uses
ServeStatic to serve files from a ``static`` directory:

.. code-block:: python

   from micropie import App
   from servestatic import ServeStatic

   class MyApp(App):
       async def index(self):
           return "Hello, world!"

   app = MyApp()

   # Mount the static file handler at the /static path
   app_with_static = ServeStatic(app, directory="static", path_prefix="/static")

When running your application, pass ``app_with_static`` to your ASGI
server instead of ``app``.  Requests to paths under ``/static`` will
be served from your ``static`` directory, while all other requests
fall through to your MicroPie routes.

Using a reverse proxy
---------------------

Alternatively, you can serve static files via a dedicated HTTP server
such as Nginx or Caddy.  In production deployments this is often the
preferred option, as a dedicated server can handle caching and
compression.  Configure your web server to serve the ``/static``
prefix directly from the filesystem and forward all other requests to
your ASGI server running MicroPie.