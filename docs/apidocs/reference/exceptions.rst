Exceptions
==========

MicroPie defines a small number of exceptions.  The most commonly
encountered is :class:`~micropie.ConnectionClosed`, used for WebSocket
disconnections.

ConnectionClosed
----------------

.. class:: ConnectionClosed

   Raised by :meth:`~micropie.WebSocket.receive_text` and
   :meth:`~micropie.WebSocket.receive_bytes` when the client closes
   the WebSocket connection.  Catch this exception to detect
   disconnection and exit your handler gracefully.  The exception does
   not carry any attributes; the WebSocket connection has already been
   closed when it is raised.

MultipartFileError
------------------

.. class:: MultipartFileError

   Raised by an uploaded file's ``content.get()`` operation when the
   multipart parser stops before that file reaches a clean end-of-file.
   This includes malformed bodies, receive timeouts and configured size
   limits.  The original parser exception is available as ``cause``.
