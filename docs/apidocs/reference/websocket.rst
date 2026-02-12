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
   :class:`~micropie.ConnectionClosed` if the client has disconnected.
   If the client sends bytes, MicroPie decodes them as UTF-8 (ignoring
   invalid sequences) and returns the decoded string.

.. method:: receive_bytes()

   Await a binary message from the client.  Returns bytes.  Raises
   :class:`~micropie.ConnectionClosed` if the client has disconnected.
   If the client sends text, MicroPie returns the UTF-8 encoded bytes.

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

MicroPie raises :class:`~micropie.ConnectionClosed` from
:meth:`receive_text` and :meth:`receive_bytes` when the client
disconnects.  See :doc:`exceptions` for exception details.
