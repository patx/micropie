Request objects
===============

.. _request-object:

MicroPie provides two request classes: :class:`~micropie.Request` for
HTTP requests and :class:`~micropie.WebSocketRequest` for WebSocket
connections.  You access the current request via
:meth:`~micropie.App.request` on your application instance or by using
the context variable in lower‑level code.

Request class
-------------

.. class:: Request(scope)

   Represents an incoming HTTP request.  The *scope* argument is the
   ASGI scope dictionary provided by the server.  You should not
   instantiate this class yourself.  MicroPie creates one per
   request and stores it in a context variable.

   .. attribute:: scope

      The original ASGI scope for the request.

   .. attribute:: method

      The HTTP method, such as ``GET`` or ``POST``.

   .. attribute:: path_params

      A list of positional path parameters.  See
      :doc:`../tutorial/routing` for details on parameter mapping.

   .. attribute:: query_params

      A ``dict`` mapping each query parameter to a list of values.
      For convenience, use ``self.request.query_params['name'][0]`` to
      obtain the first value.

   .. attribute:: body_params

      A ``dict`` mapping form field names to lists of values.  For
      JSON requests, body parameters are derived from the top‑level
      object; for ``application/x-www-form-urlencoded`` forms they are
      parsed using :func:`urllib.parse.parse_qs`.

   .. attribute:: get_json

      The JSON body parsed into a Python object.  Only populated when
      the request contains valid JSON with content type
      ``application/json``.

   .. attribute:: session

      A ``dict`` for storing per‑client data across requests.  See
      :doc:`../howto/sessions`.

   .. attribute:: files

      A ``dict`` of uploaded files for multipart/form‑data requests.
      Each entry is a mapping containing keys ``filename``,
      ``content_type`` and ``content``, where ``content`` is an
      ``asyncio.Queue`` yielding file chunks as bytes.  See
      :doc:`../tutorial/routing` for information on awaiting file fields.

   .. attribute:: headers

      A case‑insensitive mapping of header names to values, decoded as
      UTF‑8 with invalid bytes replaced.  Header names are lowercased.

WebSocketRequest class
----------------------

.. class:: WebSocketRequest(scope)

   Inherits from :class:`~micropie.Request` and represents a WebSocket
   connection request.  All attributes of :class:`~micropie.Request`
   apply.  For WebSocket handlers the request is accessible via
   ``self.request`` inside the handler or via the context variable.