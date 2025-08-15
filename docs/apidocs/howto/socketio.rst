Integrating Socket.IO
=====================

MicroPie’s built‑in WebSocket support provides a simple API for
bidirectional communication.  If you require advanced features such
as automatic reconnection, broadcasting to rooms, namespaces, or
fallback transports for browsers that do not support WebSockets, you
can integrate `python‑socketio <https://python-socketio.readthedocs.io>`_.

Socket.IO runs as an ASGI application, so you can mount it
alongside your MicroPie app and serve both under the same Uvicorn
server.  The following example shows how to set up a basic chat
application using Socket.IO with MicroPie.

.. code-block:: python

   import socketio
   from micropie import App

   # Create a Socket.IO server instance (ASGI compatible)
   sio = socketio.AsyncServer(async_mode="asgi")
   socket_app = socketio.ASGIApp(sio)

   # Create your MicroPie application
   class MyApp(App):
       async def index(self):
           # Serve an HTML page with Socket.IO client code (omitted)
           return await self._render_template("chat.html")

   app = MyApp()

   # Uvicorn accepts a single callable; wrap both apps in a simple
   # dispatcher that routes to Socket.IO on the /socket.io path
   async def application(scope, receive, send):
       if scope["path"].startswith("/socket.io"):
           await socket_app(scope, receive, send)
       else:
           await app(scope, receive, send)

Run the dispatcher with Uvicorn:

.. code-block:: console

   $ uvicorn app:application

On the client side, connect to ``/socket.io`` as usual using the
Socket.IO JavaScript client.  All other paths are handled by your
MicroPie routes.  See the ``examples/socketio`` directory in the
MicroPie source distribution for a more complete implementation that
includes HTML and JavaScript code.

Note that python‑socketio may install its own dependencies.  Consult
the Socket.IO documentation for configuration options such as
message queue back‑ends and authentication.