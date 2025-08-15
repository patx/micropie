Managing sessions
=================

MicroPie includes simple session management built on top of cookies.  A
session stores data associated with a client across multiple requests.
Sessions are useful for keeping track of login state, counters and
temporary information.

Enabling sessions
-----------------

By default, MicroPie uses an in‑memory session back‑end implemented by
:class:`~micropie.InMemorySessionBackend`.  Each session is identified
by a ``session_id`` cookie.  When the client makes a request, the
cookie is read and the session data is loaded from the back‑end.  When
you modify the session dictionary, MicroPie writes the updated
session back at the end of the request and issues a ``Set‑Cookie``
header if needed.

In order to use sessions, simply read and write the
:attr:`~micropie.Request.session` dictionary in your handler.  The
following example counts the number of visits for each client:

.. code-block:: python

   from micropie import App

   class MyApp(App):
       async def index(self):
           if "visits" not in self.request.session:
               self.request.session["visits"] = 1
           else:
               self.request.session["visits"] += 1
           return f"You have visited {self.request.session['visits']} times."

   app = MyApp()

Custom session back‑ends
------------------------

The in‑memory back‑end stores all sessions in a Python dictionary.  It
is suitable for development but will lose data when the process
terminates and cannot be shared across worker processes.  To persist
sessions in a database or cache, implement the abstract
:class:`~micropie.SessionBackend` interface:

.. code-block:: python

   from micropie import SessionBackend

   class DatabaseSessionBackend(SessionBackend):
       async def load(self, session_id: str) -> dict:
           # fetch the session from your database or cache
           data = await get_session_from_db(session_id)
           return data or {}

       async def save(self, session_id: str, data: dict, timeout: int) -> None:
           # store the session with an expiration timeout
           await save_session_to_db(session_id, data, timeout)

Assign your back‑end when constructing your application:

.. code-block:: python

   backend = DatabaseSessionBackend()
   app = MyApp(session_backend=backend)

Expiring sessions
-----------------

The global constant :data:`micropie.SESSION_TIMEOUT` controls how long
a session remains valid (in seconds).  The default is eight hours.
Back‑ends may choose to enforce this timeout in whatever manner makes
sense for their storage layer.

Security considerations
-----------------------

Sessions are sent to the client as cookies and should be treated as
untrusted input.  Avoid storing sensitive information directly in the
session.  If you implement your own back‑end, ensure that session
identifiers are random, unique and that the cookie includes the
``HttpOnly``, ``Secure`` and ``SameSite=Lax`` directives.  The
in‑memory back‑end provided by MicroPie already issues these flags.