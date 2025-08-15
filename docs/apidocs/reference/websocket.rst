WebSocket class
===============

.. _websocket-reference:

The :class:`~micropie.WebSocket` class encapsulates a WebSocket
connection.  MicroPie constructs an instance for each WebSocket
request and passes it as the first argument to your WebSocket handler.

Constructor
-----------

.. class:: WebSocket(receive, send)

   Create a new WebSocket wrapper around the ASGI ``receive`` and
   ``send`` callables.  You do not instantiate this class yourself;
   MicroPie does so internally.

Methods
-------

.. method:: accept(subprotocol=None, session_id=None)

   Accept the WebSocket connection.  You must call this method before
   sending or receiving messages.  If you provide a *session_id*,
   MicroPie sets a ``session_id`` cookie during the handshake.  The
   optional *subprotocol* argument specifies a negotiated subprotocol.

.. method:: receive_text()

   Await a text message from the client.  Returns a string.  Raises
   :class:`~micropie.ConnectionClosed` if the client has disconnected or
   ``ValueError`` if a binary message is received.

.. method:: receive_bytes()

   Await a binary message from the client.  Returns bytes.  Raises
   :class:`~micropie.ConnectionClosed` if the client has disconnected or
   ``ValueError`` if a text message is received.

.. method:: send_text(data)

   Send a text message to the client.  Raises ``RuntimeError`` if you
   have not called :meth:`accept`.

.. method:: send_bytes(data)

   Send a binary message to the client.  Raises ``RuntimeError`` if
   the connection has not been accepted.

.. method:: close(code=1000, reason=None)

   Close the WebSocket connection.  By default uses code 1000
   (normal closure).  The optional *reason* is sent to the client.

Attributes
----------

.. attribute:: accepted

   ``True`` if the WebSocket has been accepted.

.. attribute:: session_id

   The session ID set during the handshake, or ``None`` if not set.

Exceptions
----------

.. class:: ConnectionClosed

   Raised by :meth:`receive_text` and :meth:`receive_bytes` when the
   client has closed the connection.  Catch this exception in your
   handlers to perform cleanup after a disconnect.