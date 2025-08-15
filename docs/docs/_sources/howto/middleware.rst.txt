Writing middleware
==================

Middleware allows you to insert code that runs before and after your
handlers.  It is useful for cross‑cutting concerns such as logging,
authentication, rate limiting or explicit routing.  MicroPie defines
separate middleware classes for HTTP and WebSocket connections.

HTTP middleware
---------------

To create HTTP middleware, subclass :class:`~micropie.HttpMiddleware`
and implement two asynchronous methods:

* :meth:`~micropie.HttpMiddleware.before_request` – called before the
  handler is executed.  If this method returns a dictionary with
  ``status_code`` and ``body`` keys, MicroPie immediately sends that
  response and skips calling the handler.  You can also provide
  additional headers via a ``headers`` key.

* :meth:`~micropie.HttpMiddleware.after_request` – called after the
  handler has returned a response but before it is sent to the client.
  You can modify the status code, body or headers by returning a
  dictionary with updated values.

Register your middleware by appending an instance to
:attr:`~micropie.App.middlewares` on your application:

.. code-block:: python

   from micropie import App, HttpMiddleware

   class LoggingMiddleware(HttpMiddleware):
       async def before_request(self, request):
           print(f"Incoming request: {request.method} {request.scope['path']}")
           # returning None continues processing

       async def after_request(self, request, status_code, body, headers):
           print(f"Response status: {status_code}")
           # returning None uses the original response

   class MyApp(App):
       async def index(self):
           return "Hello, world!"

   app = MyApp()
   app.middlewares.append(LoggingMiddleware())

WebSocket middleware
--------------------

WebSocket middleware must subclass :class:`~micropie.WebSocketMiddleware`
and implement two methods:

* :meth:`~micropie.WebSocketMiddleware.before_websocket` – called
  before a WebSocket handler runs.  If this method returns a
  dictionary with ``code`` and ``reason``, MicroPie closes the
  connection with the given code and reason.

* :meth:`~micropie.WebSocketMiddleware.after_websocket` – called after
  the WebSocket handler completes.  Use this to perform cleanup.

Example:

.. code-block:: python

   from micropie import App, WebSocketMiddleware

   class RejectAnonymous(WebSocketMiddleware):
       async def before_websocket(self, request):
           # Reject connections without a "user" query parameter
           if "user" not in request.query_params:
               return {"code": 1008, "reason": "User name required"}

       async def after_websocket(self, request):
           print("WebSocket closed")

   class MyApp(App):
       async def ws_chat(self, ws, user):
           await ws.accept()
           await ws.send_text(f"Welcome, {user}!")
           await ws.close()

   app = MyApp()
   app.ws_middlewares.append(RejectAnonymous())

Explicit routing and other patterns
----------------------------------

You can implement custom routing schemes by writing middleware that
parses the incoming path and sets ``request._route_handler`` or
``request._ws_route_handler`` accordingly.  See the examples in the
``examples/middleware`` directory for a complete implementation.