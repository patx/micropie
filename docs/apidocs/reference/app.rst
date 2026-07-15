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

.. class:: App(session_backend=None, *, body_timeout=5.0, session_timeout=SESSION_TIMEOUT, session_cookie_secure=True)

   Create a new application.  If *session_backend* is provided it must
   be an instance of :class:`~micropie.SessionBackend`.  When omitted,
   MicroPie uses an in‑memory back‑end.

   *body_timeout* is the maximum number of seconds MicroPie waits for
   each non-multipart request-body chunk.  The timeout restarts after
   every chunk, so it limits idle time rather than total upload time.
   Set it to ``None`` to disable the framework deadline.

   *session_timeout* is passed to the session back-end whenever session
   data is saved.  *session_cookie_secure* controls whether generated
   session cookies include the ``Secure`` attribute.  It defaults to
   ``True``; applications served over plain HTTP during local development
   can set it to ``False`` explicitly.

Attributes
----------

.. attribute:: middlewares

   A list of :class:`~micropie.HttpMiddleware` instances.  Middlewares
   run before and after every HTTP request.  Append a middleware
   instance to enable it.  See :doc:`../howto/middleware` for examples.

.. attribute:: ws_middlewares

   A list of :class:`~micropie.WebSocketMiddleware` instances used for
   WebSocket connections.

.. attribute:: session_backend

   The active :class:`~micropie.SessionBackend` instance used to load
   and save session dictionaries for both HTTP and WebSocket flows.

.. attribute:: body_timeout

   The configured per-chunk idle timeout for non-multipart request
   bodies, or ``None`` when timeout enforcement is disabled.

.. attribute:: session_timeout

   The expiration timeout passed to the session back-end when HTTP or
   WebSocket session data is saved.

.. attribute:: session_cookie_secure

   Whether HTTP and WebSocket session cookies include the ``Secure``
   attribute.

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

.. attribute:: request

   The current :class:`~micropie.Request` (or
   :class:`~micropie.WebSocketRequest`) stored in a context variable for
   the active request lifecycle.

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

Framework diagnostics
---------------------

MicroPie writes framework diagnostics and exception tracebacks to the
standard ``micropie`` Python logger.  Configure this logger through the
:mod:`logging` package to integrate it with your deployment's handlers
and formatters.
