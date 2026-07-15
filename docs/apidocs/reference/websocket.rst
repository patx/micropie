WebSocket class
===============

.. _websocket-reference:

The :class:`~micropie.WebSocket` class encapsulates a WebSocket
connection.  MicroPie constructs an instance for each WebSocket
request and passes it as the first argument to your WebSocket handler.

Constructor
-----------

.. class:: WebSocket(receive, send, *, session_cookie_secure=True, session_id_validator=UUIDv4 validator)

   Create a new WebSocket wrapper around the ASGI ``receive`` and
   ``send`` callables.  You do not instantiate this class yourself;
   MicroPie does so internally and supplies the owning application's
   session-cookie policy.  Direct construction keeps secure cookies by
   default.

Methods
-------

.. method:: accept(subprotocol=None, session_id=None)

   Accept the WebSocket connection.  You must call this method before
   sending or receiving messages.  If you provide a *session_id*,
   it must pass the owning application's session-ID validator and MicroPie
   sets it as a cookie during the handshake.  The default policy requires
   canonical UUIDv4; applications with custom back-ends can configure a
   different factory and validator on :class:`~micropie.App`.  The optional
   *subprotocol* argument specifies a negotiated subprotocol.

   When no session cookie was presented, :meth:`accept` sends the fresh ID
   allocated by the application so session data written by the handler can
   be loaded on the next request.  An incoming ID whose session loads empty
   is replaced during the handshake to prevent fixation.

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

   The validated session ID allocated or loaded for this connection.  When
   the client did not present one, it is sent as a cookie by :meth:`accept`.

Exceptions
----------

MicroPie raises :class:`~micropie.ConnectionClosed` from
:meth:`receive_text` and :meth:`receive_bytes` when the client
disconnects.  See :doc:`exceptions` for exception details.
