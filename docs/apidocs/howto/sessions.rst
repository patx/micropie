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

Pass ``session_timeout`` to :class:`~micropie.App` to control how long
sessions remain valid (in seconds).  Its default is the eight-hour
:data:`micropie.SESSION_TIMEOUT` constant.  MicroPie passes the configured
value to :meth:`~micropie.SessionBackend.save` for both HTTP and WebSocket
sessions:

.. code-block:: python

   app = MyApp(session_timeout=30 * 60)  # 30 minutes

The in-memory back-end applies the supplied value independently to each
session as a sliding inactivity timeout.  Custom back-ends should likewise
honour the value passed to ``save()`` according to their storage model.

Security considerations
-----------------------

Sessions are sent to the client as cookies and should be treated as
untrusted input.  Avoid storing sensitive information directly in the
session.  If you implement your own back‑end, ensure that session
identifiers are random and unique.  MicroPie generates cookies with
``HttpOnly``, ``Secure`` and ``SameSite=Lax`` by default.

Browsers do not send ``Secure`` cookies over plain HTTP.  For local HTTP
development, disable that attribute explicitly while retaining it in
production:

.. code-block:: python

   app = MyApp(session_cookie_secure=False)

Session fixation protection
---------------------------

MicroPie validates incoming session IDs as canonical UUIDv4 values before
passing them to a back-end.  UUID validation is input hygiene; the primary
fixation defense is ID rotation.  If a request loads an empty session and
finishes with populated session data, MicroPie ignores the incoming cookie,
generates a fresh ID (UUIDv4 under the default policy), and sends it in
``Set-Cookie``.  A client-planted ID therefore cannot survive the transition
into a new authenticated session.

Applications should explicitly rotate an already populated session when
its privilege level changes, such as re-authentication or elevation to an
administrator role:

.. code-block:: python

   class MyApp(App):
       async def reauthenticate(self):
           await verify_credentials(self.request)
           self.request.session["elevated"] = True
           self.request.regenerate_session()
           return "Privileges updated"

``regenerate_session()`` preserves the session data, deletes the old
back-end entry, and persists the data under a fresh ID.  It is synchronous
and is available on HTTP requests only.

Custom session ID formats
-------------------------

The UUIDv4 policy is the secure default, but a custom back-end may already
use signed or otherwise structured IDs.  Configure both sides of that
policy together:

.. code-block:: python

   def validate_signed_id(value: str):
       return value if verify_and_parse_id(value) else None

   app = MyApp(
       session_backend=backend,
       session_id_factory=create_signed_id,
       session_id_validator=validate_signed_id,
   )

The validator must return a non-empty normalized string or ``None``; the
returned string is used as both the cookie value and the storage key.  It is
used for HTTP cookies and explicit IDs passed to
:meth:`~micropie.WebSocket.accept`.  Keep custom IDs unguessable, bounded in
length and safe for both cookies and back-end keys.  Passing
``session_id_validator=None`` disables framework validation and is intended
only when an outer trusted layer has already validated the value; ID
rotation still applies.
