Middleware classes
==================

MicroPie defines abstract base classes for writing middleware.  Use
these classes to intercept requests, implement custom routing,
authentication, logging and other cross‑cutting concerns.  See the
:doc:`../howto/middleware` guide for practical examples.

HttpMiddleware
--------------

.. class:: HttpMiddleware

   Base class for HTTP middleware.  Subclasses must implement two
   asynchronous methods:

   .. method:: before_request(request)

      Called before the HTTP handler runs.  *request* is the
      :class:`~micropie.Request` object.  Return a dictionary
      ``{"status_code": status, "body": body, "headers": headers}``
      to short‑circuit the request and send a response immediately.  To
      continue processing, return ``None``.

   .. method:: after_request(request, status_code, response_body, extra_headers)

      Called after the handler has completed but before the response
      is sent.  You may return a dictionary with updated
      ``status_code``, ``body`` and ``headers``.  Return ``None`` to
      leave the response unchanged.

WebSocketMiddleware
-------------------

.. class:: WebSocketMiddleware

   Base class for WebSocket middleware.  Subclasses must implement
   these methods:

   .. method:: before_websocket(request)

      Called before a WebSocket handler runs.  *request* is a
      :class:`~micropie.WebSocketRequest` object.  Return a dictionary
      ``{"code": code, "reason": reason}`` to reject the connection
      with the given close code and reason.  Return ``None`` to allow
      the connection.

   .. method:: after_websocket(request)

      Called after the WebSocket handler completes.  Use this to
      release resources or log activity.  Return value is ignored.