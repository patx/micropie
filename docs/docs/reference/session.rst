Session back‑ends
=================

MicroPie abstracts session storage behind the :class:`~micropie.SessionBackend`
interface.  Different back‑ends may store session data in memory,
databases, caches or external services.  A session is a dictionary of
key/value pairs associated with a ``session_id`` cookie.

SessionBackend
--------------

.. class:: SessionBackend

   Abstract base class for session storage.  Implementations must
   provide the following asynchronous methods:

   .. method:: load(session_id)

      Load session data for the given *session_id*.  Return a
      dictionary of session data or an empty dictionary if the session
      does not exist or has expired.

   .. method:: save(session_id, data, timeout)

      Persist the *data* dictionary for the given *session_id* with
      an expiry time of *timeout* seconds.

InMemorySessionBackend
----------------------

.. class:: InMemorySessionBackend

   Concrete implementation of :class:`SessionBackend` that stores
   sessions in memory.  This back‑end is appropriate for development
   and testing but does not persist data across process restarts and
   cannot be shared among worker processes.

   .. method:: __init__()

      Create an empty in‑memory session store.

   .. method:: load(session_id)

      Return the session dictionary if it exists and has not expired
      according to :data:`micropie.SESSION_TIMEOUT`, otherwise return
      an empty dictionary.

   .. method:: save(session_id, data, timeout)

      Store *data* under *session_id* and update the last access time.

SESSION_TIMEOUT
---------------

.. data:: SESSION_TIMEOUT

   The default session expiration time in seconds (eight hours).  You
   can override this constant in your own code before importing
   MicroPie or by passing a different timeout when saving sessions in
   a custom back‑end.

See also the :doc:`../howto/sessions` guide for examples of using and
implementing session back‑ends.