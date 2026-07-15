Routing and handlers
====================

MicroPie maps incoming HTTP requests to methods on your :class:`~micropie.App`
subclass.  This section explains how the mapping works and how your
handlers receive input from the URL path, query strings, form data and
JSON bodies.  Session state is accessed explicitly through the request.

URL to function mapping
-----------------------

When an HTTP request arrives, MicroPie extracts the path portion of the
URL and uses the first path segment to determine which method should
handle the request.  For example, a GET request to ``/greet`` calls
``greet`` on your :class:`~micropie.App` subclass.  A request to the
root URL ``/`` calls ``index``.  Only methods that do not start with
an underscore are exposed as route handlers.  Prefacing a method name
with an underscore makes it private and hides it from external
requests.

Handlers may be synchronous or asynchronous functions.  They return
either a string, bytes, a JSON‑serialisable object, a tuple of
``(status_code, body)`` or ``(status_code, body, headers)``, or an
iterator/generator for streaming responses.  See
:doc:`../howto/streaming` for details on streaming.

Parameters and arguments
------------------------

MicroPie automatically populates handler arguments from several
sources in the following order:

1. **Path parameters** – Additional path segments after the first map to
   positional parameters.  For example:

   .. code-block:: python

      class AppExample(App):
          async def greet(self, name):
              return f"Hello, {name}!"

   Visiting ``/greet/Alice`` passes ``"Alice"`` as the ``name`` argument.
   You can also use ``*args`` to capture an arbitrary number of path
   segments.

2. **Query parameters** – Named parameters in the query string fill
   keyword arguments when path parameters are exhausted.  For example,
   ``/greet?name=Alice`` also passes ``"Alice"`` to the ``name``
   parameter.

3. **Body data** – For POST, PUT and PATCH requests, form fields populate
   handler arguments as strings.  Keys from a top-level JSON object also
   bind by name, retaining their native JSON types, including nested
   objects, arrays, numbers, booleans and ``null``.

4. **Files** – If the request is multipart/form‑data, uploaded files
   appear in :attr:`~micropie.Request.files`.  You can declare a file
   argument in your handler signature to receive a file object.

5. **Default values** – If no request source provides a value, default
   values in your function signature are used.

If MicroPie cannot determine a value for a required parameter, it
returns a ``400 Bad Request``.

Session values never participate in automatic argument binding.  This
keeps untrusted request inputs and trusted session state in separate
namespaces.  Read session values explicitly inside the handler:

.. code-block:: python

   class MyApp(App):
       async def transfer(self, amount):
           user_id = self.request.session["user_id"]
           return await make_transfer(user_id, amount)

An extra ``user_id`` query or body field cannot replace the value read
from the session in this example.

Choosing an input access style
------------------------------

MicroPie gives you three levels of request input access.  Prefer the
simplest level that fits the handler.

1. **Handler arguments** are the most concise option.  Use them when an
   endpoint needs a small number of named values and the normal binding
   order is acceptable.

   .. code-block:: python

      class MyApp(App):
          async def search(self, q="", page="1"):
              return {"q": q, "page": int(page)}

   This works for ``/search?q=micropie&page=2`` without touching
   ``self.request`` directly.

2. **Helper methods** are best when the handler needs explicit control
   over where a value comes from, a default value, or the full JSON
   payload.

   .. code-block:: python

      class MyApp(App):
          async def search(self):
              q = self.request.query("q", "")
              page = int(self.request.query("page", "1"))
              return {"q": q, "page": page}

          async def submit(self):
              username = self.request.form("username", "Anonymous")
              return {"submitted_by": username}

          async def api_submit(self):
              payload = self.request.json()
              username = self.request.json("username", "Anonymous")
              return {"submitted_by": username, "raw": payload}

   The helper methods are:

   * ``self.request.query(name, default=None)``: first query-string
     value for ``name``.
   * ``self.request.form(name, default=None)``: first parsed body value
     for ``name`` from URL-encoded or multipart form data.
   * ``self.request.json(name=None, default=None)``: full parsed JSON
     payload when called with no name, or one top-level JSON object value
     when ``name`` is provided.

3. **Raw attributes** are useful when you need the lower-level parsed
   structures, such as repeated query parameters, all submitted form
   values, uploaded files, or middleware decisions.

   * ``self.request.path_params``: list of positional path segments.
   * ``self.request.query_params``: ``dict[str, list[str]]`` parsed from
     the query string.
   * ``self.request.body_params``: ``dict[str, list[str]]`` parsed from
     form-urlencoded payloads or multipart text fields.  JSON data is
     available only through ``json()`` and native JSON argument binding.
   * ``self.request.session``: session dictionary.
   * ``self.request.files``: uploaded multipart files.
   * ``self.request.headers``: lower-case request header mapping.

   For example, use ``query_params`` when repeated values matter:

   .. code-block:: python

      class MyApp(App):
          async def filter(self):
              tags = self.request.query_params.get("tag", [])
              return {"tags": tags}

Query strings and URL-encoded forms are parsed strictly.  Empty values
such as ``name=`` are preserved, while fields without ``=``, invalid
percent escapes and invalid UTF-8 receive ``400 Bad Request``.  A
WebSocket request with a malformed query string is closed with code
``1008``.

Do not await request helpers
----------------------------

The request helper methods are synchronous accessors over data MicroPie
has already parsed for the current request.  Do not use ``await`` with
``query()``, ``form()`` or ``json()``:

.. code-block:: python

   class MyApp(App):
       async def submit(self):
           data = self.request.json()
           username = self.request.form("username", "")
           q = self.request.query("q", "")
           return {"data": data, "username": username, "q": q}

For JSON and URL-encoded form requests, the body has been read before
your handler runs.  Multipart file uploads are the main exception:
uploaded file content is exposed as an ``asyncio.Queue`` in
``self.request.files`` and should be read asynchronously.

Examples
--------

The following examples illustrate common patterns:

.. code-block:: python

   class MyApp(App):
       async def greet(self, name="Guest"):
           """Return a greeting for a named visitor.

           If the ``name`` argument is not provided via the path or
           query parameters, ``"Guest"`` is used as a default.
           """
           return f"Hello, {name}!"

       async def add(self, x, y):
           """Add two numbers provided via path segments.

           Example: ``/add/2/3`` returns ``5``.
           """
           return str(int(x) + int(y))

       async def submit(self, username="Anonymous"):
           """Handle a form submission.

           This handler accepts POST requests and uses the
           ``username`` field from the request body.
           """
           return f"Form submitted by: {username}"

See :ref:`Request objects <request-object>` for the attributes
available on the current request and :ref:`App class <app-class>` for
details about the ``App`` class.

HTTP methods and responses
--------------------------

Handlers run for any HTTP method unless you explicitly check
``self.request.method`` inside the handler.  It is your
responsibility to dispatch based on the method if your endpoint should
behave differently for GET and POST.  Handlers may return:

* A string or bytes – sent as the body of the response with a
  ``200 OK`` status.
* A JSON‑serialisable object – automatically encoded into JSON and
  returned with a ``Content‑Type`` of ``application/json``.
* A tuple ``(status_code, body)`` – sets the HTTP status and body.
* A tuple ``(status_code, body, headers)`` – sets status, body and
  additional headers.  Headers should be a list of ``(name, value)`` pairs.
* A generator or async generator – streams chunks to the client.  Use
  this for large responses or server‑sent events.

Advanced routing
----------------

You can implement explicit routing, path prefixing or complex
dispatching by writing a custom :class:`~micropie.HttpMiddleware`.  See
the :doc:`../howto/middleware` guide and the examples in the
``examples/explicit_routing`` directory of the source distribution.
