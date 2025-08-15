Routing and handlers
====================

MicroPie maps incoming HTTP requests to methods on your :class:`~micropie.App`
subclass.  This section explains how the mapping works and how your
handlers receive input from the URL path, query strings, form data and
sessions.

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
:doc:`howto/streaming` for details on streaming.

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

3. **Body/form data** – For POST, PUT and PATCH requests, form fields
   populate handler arguments.  JSON bodies are decoded into a
   dictionary of key/value pairs.

4. **Files** – If the request is multipart/form‑data, uploaded files
   appear in :attr:`~micropie.Request.files`.  You can declare a file
   argument in your handler signature to receive a file object.

5. **Session data** – Values stored in :attr:`~micropie.Request.session`
   fill remaining parameters.  See :doc:`howto/sessions` for details.

6. **Default values** – If no other source provides a value, default
   values in your function signature are used.

If MicroPie cannot determine a value for a required parameter, it
returns a ``400 Bad Request``.

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

See :ref:`request-object` for the attributes available on the current
request and :ref:`app-class` for details about the ``App`` class.

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
the :doc:`howto/middleware` guide and the examples in the
``examples/explicit_routing`` directory of the source distribution.