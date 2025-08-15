Glossary
========

This glossary defines terms used throughout the MicroPie documentation.

.. glossary::

   ASGI
     The Asynchronous Server Gateway Interface.  A standard for
     asynchronous communication between Python applications and
     servers.  MicroPie applications implement the ASGI call
     interface.  See the `ASGI specification <https://asgi.readthedocs.io>`_.

   route handler
     A method on your :class:`~micropie.App` subclass that handles an
     incoming HTTP request.  The first segment of the URL path maps to
     the handler name, and remaining segments or query parameters map
     to arguments.  Handlers may be synchronous or asynchronous.

   session
     A dictionary of data associated with a client across multiple
     requests.  MicroPie stores the session in a pluggable back‑end
     and identifies it using a ``session_id`` cookie.  See
     :doc:`howto/sessions`.

   middleware
     Code that runs before and/or after a request handler.  Middleware
     can short‑circuit requests, modify responses, enforce security
     policies or implement custom routing.  MicroPie defines
     :class:`~micropie.HttpMiddleware` and
     :class:`~micropie.WebSocketMiddleware` base classes.

   WebSocket
     A persistent, bidirectional communication channel over TCP.  In
     MicroPie, WebSocket handlers are methods prefixed with ``ws_``.
     They receive an instance of :class:`~micropie.WebSocket` and
     optionally additional parameters.  See :doc:`tutorial/websockets`.

   context variable
     An object from the :mod:`contextvars` module that stores data
     local to the current asynchronous context.  MicroPie stores the
     current request in a context variable so it is accessible via
     :meth:`~micropie.App.request` without passing it through your
     function calls.