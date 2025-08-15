App class
=========

.. _app-class:

The :class:`~micropie.App` class is the core of a MicroPie application.
It implements the ASGI call interface and dispatches HTTP, WebSocket
and lifespan events to your handlers.  Subclass :class:`~micropie.App`
and add public methods to create route handlers.  Instantiate your
subclass and pass the resulting object to an ASGI server such as
Uvicorn.

Constructor
-----------

.. class:: App(session_backend=None)

   Create a new application.  If *session_backend* is provided it must
   be an instance of :class:`~micropie.SessionBackend`.  When omitted,
   MicroPie uses an in‑memory back‑end.

Attributes
----------

.. attribute:: middlewares

   A list of :class:`~micropie.HttpMiddleware` instances.  Middlewares
   run before and after every HTTP request.  Append a middleware
   instance to enable it.  See :doc:`../howto/middleware` for examples.

.. attribute:: ws_middlewares

   A list of :class:`~micropie.WebSocketMiddleware` instances used for
   WebSocket connections.

.. attribute:: startup_handlers

   A list of asynchronous callables that run during the ASGI
   ``lifespan.startup`` event.  Use this to set up resources such as
   database connections.  See :doc:`../tutorial/quickstart` for an
   example.

.. attribute:: shutdown_handlers

   A list of asynchronous callables that run during the ASGI
   ``lifespan.shutdown`` event.  Use this to clean up resources.

Methods
-------

.. method:: __call__(scope, receive, send)

   The ASGI entry point.  Dispatches to HTTP, WebSocket or lifespan
   handlers based on ``scope['type']``.  You normally do not call this
   directly; the ASGI server calls it for you.

.. method:: request

   Return the current :class:`~micropie.Request` object.  This is
   stored in a context variable so that it is available throughout
   asynchronous callbacks.

.. method:: _redirect(location, extra_headers=None)

   Return a tuple ``(302, '', headers)`` representing an HTTP redirect
   to *location*.  Use this helper in your handlers to redirect the
   client.

.. method:: _render_template(name, **kwargs)

   Render a Jinja2 template asynchronously.  Returns a string
   containing the rendered output.  Requires Jinja2 to be installed.
   See :doc:`../howto/templates` for details.

Additionally, MicroPie defines several private helper methods such as
``_parse_cookies`` and ``_send_response``.  These are considered
internal and not part of the public API.  They may change without
notice.