Architecture and design
=======================

MicroPie is intentionally small.  Its goal is to provide just enough
functionality to build asynchronous web applications without locking
you into a rigid structure.  This section discusses some of the key
design choices and how they influence the API.

ASGI application
----------------

MicroPie is built on top of the `ASGI`_ specification, which defines
how Python applications communicate with asynchronous servers.  Your
application subclass inherits from :class:`~micropie.App` and
implements the ASGI call interface via the ``__call__`` method.  The
framework inspects the ``scope['type']`` field to dispatch to HTTP,
WebSocket or lifespan handling code.

Routing by naming
-----------------

Unlike frameworks that require you to declare routes in advance,
MicroPie derives routing information from the names of your methods.
The first segment of the path becomes the handler name.  This allows
you to add new endpoints simply by defining a new method on your
application subclass.  The remaining path segments, query string
parameters and form data are mapped to arguments via function
signature inspection.  This approach reduces boilerplate but may
surprise users expecting explicit routing.  You can always regain
control by writing a custom middleware to map paths to handlers or by
checking ``self.request.method`` and ``self.request.path_params`` inside
your handlers.

Context‑local request
---------------------

MicroPie stores the current request in a :mod:`contextvars`
ContextVar.  This allows you to access ``self.request`` within your
handler as well as from deeper helper functions without passing the
request around explicitly.  The context variable is reset at the end
of each request to avoid leaking state.

Session management
------------------

Sessions are stored in a pluggable back‑end and identified by a
random ``session_id`` cookie.  The default in‑memory back‑end keeps
session data in dictionaries keyed by session ID and updates a last
access timestamp to implement expiration.  You can customise the
back‑end by providing your own implementation of
:class:`~micropie.SessionBackend`.  MicroPie saves sessions after a
handler returns, only if ``self.request.session`` is non‑empty, to
avoid creating unnecessary cookies.

Middleware pipeline
-------------------

The middleware hooks allow you to intercept requests before and after
handlers.  Middleware can modify the request object, provide early
responses (useful for authentication), and alter the final response.
For WebSockets, separate middleware hooks run before the connection
handler starts and after it finishes.

Streaming and SSE support
-------------------------

Handlers may return an iterator or asynchronous generator to stream
data to the client.  MicroPie detects such responses and iterates
over them, sending each chunk to the client.  When using server‑sent
events (SSE) there is an additional challenge: if the client
disconnects, the iterator must be cancelled.  MicroPie wraps SSE
responses in a small loop that listens for disconnect events and
cancels the generator accordingly.  Remember to include a
``Content‑Type: text/event-stream`` header when sending SSE.

Error handling
--------------

MicroPie automatically handles common error cases.  Requests for
unknown routes result in a ``404 Not Found``.  If a required
parameter is missing, MicroPie responds with ``400 Bad Request``.
Unhandled exceptions inside handlers produce a ``500 Internal Server
Error`` and are printed to standard error.  You can override these
behaviours via middleware.

Extensibility
-------------

The minimalist core is designed to be extended.  You can mount your
application behind other ASGI middleware, integrate additional
protocols like Socket.IO, or implement your own session storage.  The
framework imposes few constraints so that you remain in control of
your stack.

.. _ASGI: https://asgi.readthedocs.io/