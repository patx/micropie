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

.. class:: App(session_backend=None, *, body_timeout=5.0, max_body_size=16777216, max_form_field_size=1048576, session_timeout=SESSION_TIMEOUT, session_cookie_secure=True, session_id_factory=UUIDv4 factory, session_id_validator=UUIDv4 validator)

   Create a new application.  If *session_backend* is provided it must
   be an instance of :class:`~micropie.SessionBackend`.  When omitted,
   MicroPie uses an in‑memory back‑end.

   *body_timeout* is the maximum number of seconds MicroPie waits for
   each request-body chunk, including multipart uploads.  The timeout
   restarts after every chunk, so it limits idle time rather than total upload time.
   Set it to ``None`` to disable the framework deadline.

   *max_body_size* limits the total encoded request body to 16 MiB by
   default.  MicroPie rejects an oversized ``Content-Length`` before
   reading the body and also counts actual chunks, covering requests
   without that header.  *max_form_field_size* separately limits each
   accumulated multipart text field to 1 MiB while allowing file content
   to remain streamed.  Either limit can be disabled with ``None``.
   Multipart file producers use nonblocking queues so later parts cannot
   deadlock behind an undrained file; consequently, ``max_body_size`` is
   also the request-wide payload-byte bound for queued upload content.
   Disabling it permits unbounded buffering when a handler does not consume
   files.

   *session_timeout* is passed to the session back-end whenever session
   data is saved.  *session_cookie_secure* controls whether generated
   session cookies include the ``Secure`` attribute.  It defaults to
   ``True``; applications served over plain HTTP during local development
   can set it to ``False`` explicitly.

   By default, *session_id_factory* creates UUIDv4 values and
   *session_id_validator* accepts only canonical UUIDv4 strings.  A custom
   storage back-end that owns another identifier format can provide a
   factory and validator; a validator returns the normalized ID or ``None``
   to reject it.  Setting the validator itself to ``None`` accepts any
   non-empty cookie value and should only be used with another trusted
   validation boundary.

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

   The configured per-chunk idle timeout for buffered and multipart
   request bodies, or ``None`` when timeout enforcement is disabled.

.. attribute:: max_body_size

   Maximum total encoded request-body size in bytes, or ``None``.  Bodies
   exceeding the limit receive ``413 Payload Too Large``.

.. attribute:: max_form_field_size

   Maximum size in bytes of each multipart text field, or ``None``.
   This is independent of the total body limit so applications permitting
   large streamed files need not permit equally large in-memory fields.

.. attribute:: session_timeout

   The expiration timeout passed to the session back-end when HTTP or
   WebSocket session data is saved.

.. attribute:: session_cookie_secure

   Whether HTTP and WebSocket session cookies include the ``Secure``
   attribute.

.. attribute:: session_id_factory

   Callable used whenever MicroPie needs a fresh session ID.

.. attribute:: session_id_validator

   Callable that normalizes an incoming or generated session ID and
   returns ``None`` to reject it.  The default requires canonical UUIDv4.

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
   client.  Absolute URLs are allowed, so do not pass an untrusted target
   without an application-level allow-list.  MicroPie percent-encodes
   non-ASCII URL components, but applications constructing query strings
   should still use :func:`urllib.parse.urlencode` rather than concatenation.

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

Body-limit placement
--------------------

MicroPie's :class:`~micropie.HttpMiddleware` hooks run after request-body
parsing starts and do not receive the ASGI ``receive`` callable.
They therefore cannot safely implement a byte-counting body limit.  Use
the application settings above for framework enforcement.  A reverse
proxy limit or outer ASGI middleware that wraps ``receive`` remains useful
as an additional deployment boundary.
