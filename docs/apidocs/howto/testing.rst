Testing MicroPie applications
=============================

This guide shows practical approaches for testing MicroPie applications.
MicroPie does not ship with a bespoke test client, but because it is a
regular ASGI application you can exercise it using familiar Python
libraries such as :mod:`unittest`, :mod:`pytest` and
:mod:`httpx`'s ASGI tools.

Choosing a test framework
-------------------------

MicroPie itself uses :class:`unittest.IsolatedAsyncioTestCase` in
``tests.py`` to run asynchronous tests. ``pytest`` with the
``pytest-asyncio`` plugin offers a similar developer experience. Pick the
library that best matches your project's conventions—the examples below
work with either.

Unit testing handlers directly
------------------------------

Because handlers are regular functions, you can instantiate your
:class:`~micropie.App` subclass and call methods directly. Use the
:func:`micropie.current_request` context variable to set up any request
state that your handler expects.

.. code-block:: python

   from contextvars import Token

   from micropie import App, Request, current_request

   class MyApp(App):
       async def greet(self, name="World"):
           return f"Hello {name}!"

   async def test_greet_uses_default():
       app = MyApp()
       scope = {"type": "http", "method": "GET", "path": "/"}
       request = Request(scope)
       token: Token = current_request.set(request)
       try:
           response = await app.greet()
       finally:
           current_request.reset(token)
       assert response == "Hello World!"

Testing through the ASGI interface
----------------------------------

For higher confidence, drive the full ASGI stack. ``httpx`` provides an
``ASGITransport`` class that can mount a MicroPie app. Install ``httpx``
with ``pip install httpx``. The example below uses ``pytest`` style
asserts, but the structure works in ``unittest`` with
``self.assertEqual``.

.. code-block:: python

   import pytest
   import httpx

   from micropie import App

   class MyApp(App):
       async def index(self):
           return {"status": "ok"}

   @pytest.mark.asyncio
   async def test_index_returns_json():
       app = MyApp()
       async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
           response = await client.get("http://test/" )
       assert response.status_code == 200
       assert response.json() == {"status": "ok"}

Simulating sessions and middleware
----------------------------------

To assert session behaviour, populate ``scope["headers"]`` with a
``cookie`` header and inspect the response headers for the updated
``Set-Cookie`` value. Middleware can be tested by attaching it to your
app instance before issuing requests.

.. code-block:: python

   from micropie import App, HttpMiddleware

   class AddHeader(HttpMiddleware):
       async def after_request(self, request, response):
           response.setdefault("headers", []).append((b"x-test", b"1"))
           return response

   class MyApp(App):
       async def index(self):
           return "hi"

   async def test_middleware_header():
       app = MyApp()
       app.middleware.append(AddHeader())
       transport = httpx.ASGITransport(app=app)
       async with httpx.AsyncClient(transport=transport) as client:
           response = await client.get("http://test/")
       assert response.headers["x-test"] == "1"

Handling lifespan events
------------------------

If your application registers startup or shutdown handlers, wrap your
ASGI client in a lifespan manager. ``httpx`` exposes
:class:`httpx.ASGITransport` with a ``lifespan="auto"`` mode that will
run lifespan events before the first request and after the client exits.

.. code-block:: python

   async with httpx.AsyncClient(
       transport=httpx.ASGITransport(app=app, lifespan="auto")
   ) as client:
       ...

Further reading
---------------

* Browse ``tests.py`` in the MicroPie source tree for additional
  patterns, including WebSocket testing helpers.
* The `httpx documentation <https://www.python-httpx.org/advanced/#calling-into-python-web-apps>`_
  has more on driving ASGI apps from tests.
