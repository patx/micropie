Streaming responses
===================

For long‑running tasks or large responses it is often desirable to
stream data to the client in chunks rather than return a single
buffer.  MicroPie supports streaming by allowing your handler to
return an iterator or asynchronous generator.  Each chunk yielded by
the generator is sent as part of the response body.  When the
generator finishes, MicroPie automatically sends an empty chunk to
signal completion.

Example: number stream
----------------------

The following handler streams a sequence of numbers to the client one
per second:

.. code-block:: python

   from micropie import App
   import asyncio

   class MyApp(App):
       async def numbers(self):
           async def generator():
               for i in range(5):
                   yield f"Number: {i}\n"
                   await asyncio.sleep(1)
           return generator()

   app = MyApp()

Visiting ``/numbers`` will produce output like:

.. code-block:: text

   Number: 0
   Number: 1
   Number: 2
   Number: 3
   Number: 4

MicroPie automatically sets ``Content‑Type`` to ``text/html`` if you
do not specify a content type.  You can override or add headers by
returning a tuple ``(status_code, body, headers)`` and making the
generator the body.

Handling client disconnects
---------------------------

If the client disconnects while a generator is running, MicroPie
cancels the generator and closes the underlying response.  This
behaviour is important for long‑lived streams such as server‑sent
events (SSE).  When writing a generator, use ``try``/``finally`` or
``async with`` to perform cleanup when the stream is cancelled.

Server‑sent events
------------------

MicroPie treats any iterable response body as a general stream.
Implementing true server‑sent events requires you to set the
``Content‑Type`` header to ``text/event-stream`` and send
properly‑formatted SSE messages (``data: ...\n\n``).  Additionally,
MicroPie includes a patch that handles early disconnection of SSE
clients in its HTTP handling code.  For a full example, see the
``examples/sse`` directory in the MicroPie source distribution.