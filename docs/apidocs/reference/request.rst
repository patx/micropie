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

   The helper methods on ``Request`` are synchronous.  Use
   ``request.query(...)``, ``request.form(...)`` and ``request.json(...)``
   directly, even inside ``async def`` handlers.  They return values that
   MicroPie has already parsed for the current request.

   .. attribute:: scope

      The original ASGI scope for the request.

   .. attribute:: method

      The HTTP method, such as ``GET`` or ``POST``.

   .. attribute:: path_params

      A list of positional path parameters.  See
      :doc:`../tutorial/routing` for details on parameter mapping.
      You usually do not need this directly because MicroPie binds path
      parameters into handler arguments first.

   .. attribute:: query_params

      A ``dict`` mapping each query parameter to a list of values.
      This is the raw parsed mapping from the query string.  For
      convenience, use :meth:`~micropie.Request.query` to obtain
      the first value.

      Use this raw attribute when repeated query parameters matter:

      .. code-block:: python

         tags = request.query_params.get("tag", [])

   .. method:: query(name, default=None)

      Return the first value for query parameter *name*, or *default*
      if missing.

      This is the usual API for optional query-string inputs:

      .. code-block:: python

         page = int(request.query("page", "1"))

      Do not await this method.

   .. attribute:: body_params

      A ``dict`` mapping form field names to lists of values.  For
      JSON requests, body parameters are derived from the top-level
      object; for ``application/x-www-form-urlencoded`` forms they are
      parsed using :func:`urllib.parse.parse_qs`.  This is the raw
      mapping used by MicroPie for argument binding.

      Use this raw attribute when you need all submitted values for a
      field, or when middleware needs to inspect parsed request fields:

      .. code-block:: python

         selected = request.body_params.get("choice", [])

   .. method:: form(name, default=None)

      Return the first value for form/body field *name*, or *default*
      if missing.

      This helper reads from :attr:`body_params`, so it returns the
      first parsed body value.  It is commonly used for HTML form fields,
      but top-level JSON object keys are also mirrored into
      :attr:`body_params` for argument binding.

      .. code-block:: python

         username = request.form("username", "Anonymous")

      Do not await this method.

   .. method:: json(name=None, default=None)

      Return the parsed JSON payload or a value from a top-level JSON
      object.

      If *name* is omitted, this method returns the full parsed payload.
      If *name* is provided and the payload is an object, the value for
      that key is returned; otherwise *default* is returned.

      .. code-block:: python

         payload = request.json()
         username = request.json("username", "Anonymous")

      Do not await this method.  MicroPie parses JSON before calling the
      route handler.  Invalid JSON requests receive ``400 Bad Request``.

   .. attribute:: session

      A ``dict`` for storing per‑client data across requests.  See
      :doc:`../howto/sessions`.

   .. attribute:: files

      A ``dict`` of uploaded files for multipart/form-data requests.
      Each entry is a mapping containing keys ``filename``,
      ``content_type`` and ``content``, where ``content`` is an
      ``asyncio.Queue`` yielding file chunks as bytes.  See
      :doc:`../tutorial/routing` for information on awaiting file fields.

      Unlike ``query()``, ``form()`` and ``json()``, file content is
      streaming data.  Read file chunks asynchronously from the
      ``content`` queue.

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
