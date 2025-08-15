WebSocket support
=================

MicroPie includes first‑class support for WebSockets.  WebSockets are a
persistent, bidirectional communication channel over a single TCP
connection.  They enable real‑time applications such as chat, live
notifications and collaborative editing.

Mapping WebSocket routes
------------------------

WebSocket handlers live on the same :class:`~micropie.App` subclass
that serves your HTTP routes.  The naming convention is similar to
HTTP handlers, but with a ``ws_`` prefix.  For example, a method
called ``ws_chat`` handles WebSocket connections at ``/chat``.  If the
path is empty, ``ws_index`` handles the root WebSocket route.

When a WebSocket connection is initiated, MicroPie constructs a
:class:`~micropie.WebSocket` object and passes it as the first
argument to your handler, along with any path or query parameters.  A
typical handler must call :meth:`~micropie.WebSocket.accept` to accept
the connection and then use :meth:`~micropie.WebSocket.receive_text`
and :meth:`~micropie.WebSocket.send_text` (or their ``bytes``
counterparts) to communicate.

Example: echo server
--------------------

The example below implements a simple echo server.  The server
accepts the WebSocket connection and then echoes back whatever text it
receives.  When the client disconnects, the handler finishes.

.. code-block:: python

   from micropie import App

   class MyApp(App):
       async def ws_echo(self, ws):
           # Accept the connection; without this call, MicroPie will
           # automatically reject the WebSocket.
           await ws.accept()
           while True:
               try:
                   message = await ws.receive_text()
               except ConnectionClosed:
                   # Client closed the connection
                   break
               # Send the same message back to the client
               await ws.send_text(f"Echo: {message}")

   app = MyApp()

To test this endpoint, run your application and connect to
``ws://127.0.0.1:8000/echo`` using a WebSocket client.  Most modern
browsers support WebSockets via JavaScript.

Accessing query and path parameters
-----------------------------------

Just like HTTP handlers, WebSocket handlers receive path and query
parameters.  Additional positional arguments come from the path, and
keyword arguments are filled from the query string or session.  For
example:

.. code-block:: python

   class MyApp(App):
       async def ws_greet(self, ws, name="Guest"):
           await ws.accept()
           await ws.send_text(f"Hello {name}!")
           await ws.close()

Connecting to ``ws://localhost:8000/greet/Alice`` sends back
``"Hello Alice!"``.  Connecting to ``ws://localhost:8000/greet?name=Bob``
sends ``"Hello Bob!"``.  See :ref:`websocket-reference` for the
complete API of the :class:`~micropie.WebSocket` class.

Integrating Socket.IO
---------------------

MicroPie focuses on the core WebSocket protocol.  If you need more
advanced real‑time features—automatic reconnection, broadcasting, or
fallback transports such as polling—you can integrate
`python‑socketio <https://python-socketio.readthedocs.io>`_.  See the
``examples/socketio`` directory in the MicroPie source distribution for
sample code and instructions.  When integrating Socket.IO, you still
run your MicroPie application behind an ASGI server and attach the
Socket.IO server as additional middleware or route.