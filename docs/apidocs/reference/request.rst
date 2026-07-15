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
      the first value.  Parsing is permissive for compatibility: blank
      and bare fields are omitted, while malformed encoding is tolerated.

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

      A ``dict`` mapping URL-encoded and multipart form field names to
      lists of string values.  JSON objects are not mirrored into this
      mapping; use :meth:`json` for JSON access.  URL-encoded form bodies
      use the same permissive parsing as query strings: blank and bare
      fields are omitted, while malformed encoding is tolerated.

      Use this raw attribute when you need all submitted values for a
      field, or when middleware needs to inspect parsed request fields:

      .. code-block:: python

         selected = request.body_params.get("choice", [])

   .. method:: form(name, default=None)

      Return the first URL-encoded or multipart form value for *name*,
      or *default* if missing.

      This helper reads from :attr:`body_params`, so it returns the
      first parsed form value.  It does not read JSON objects.

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
      Top-level JSON object keys can bind directly to handler arguments
      and retain native JSON types; nested values are not stringified.

   .. method:: regenerate_session()

      Mark the current HTTP session for ID rotation when the response is
      persisted.  Existing session data is preserved, the old back-end
      entry is deleted, and a fresh session cookie is issued using the
      application's configured ID factory.  Call this
      after a privilege change in an already populated session.  Do not
      await this method.

   .. attribute:: session

      A ``dict`` for storing per‑client data across requests.  See
      :doc:`../howto/sessions`.  Session values are deliberately excluded
      from automatic handler argument binding; access them explicitly
      through this attribute.

   .. attribute:: files

      A ``dict`` of uploaded files for multipart/form-data requests.
      Each entry is a mapping containing keys ``filename``,
      ``content_type`` and ``content``, where ``content`` is an
      ``asyncio.Queue`` subclass yielding file chunks as bytes.  See
      :doc:`../tutorial/routing` for information on awaiting file fields.

      Unlike ``query()``, ``form()`` and ``json()``, file content is
      streaming data.  Read file chunks asynchronously from the
      ``content`` queue.  A complete file ends with ``None``.  If parsing,
      timeout or body-limit enforcement aborts an open file, ``get()``
      raises :class:`~micropie.MultipartFileError` instead; do not treat
      parser failure as a clean end-of-file.

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
