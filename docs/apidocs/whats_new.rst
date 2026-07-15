.. _release-notes:

What's new in MicroPie
======================

This page summarises noteworthy changes in recent MicroPie releases. It
is not an exhaustive changelog, but it highlights the features and bug
fixes most likely to affect application developers. For the full list of
releases, consult the `GitHub releases page <https://github.com/patx/micropie/releases>`_.

Version highlights
------------------

* **0.32** – Adds request-body and multipart-field limits,
  per-chunk timeouts for buffered and multipart bodies, deadlock-free
  multi-file streaming, explicit multipart failure signaling, session
  fixation protection, configurable session cookie/ID policies, isolated
  session argument binding, native JSON argument values, and structured
  framework logging.  It also fixes keyword-only/``**kwargs`` binding,
  WebSocket session-cookie delivery, pending streaming receive tasks,
  multipart sub-application handoff, and response-header encoding failures.
* **0.31** – Hardens route lookup so non-callable public attributes and
  property-like descriptors are not treated as handlers. Descriptor-backed
  route methods such as ``functools.partialmethod`` continue to work after
  binding.
* **0.30** – Removes the public ``Request.get_json`` attribute. Use
  ``Request.json()`` for the full parsed JSON payload or
  ``Request.json(name, default)`` for top-level object lookups.
* **0.29** Performance upgrades, no more per request signature inspections
  for routing. 24%-54% increase in req/sec.
* **0.28** – Adds ``Request.json`` helper for convenient JSON access and
  updates routing docs to show both automatic argument binding and
  helper-based request access patterns.
* **0.27** – Adds ``Request.query`` and ``Request.form`` helpers for more
  direct access to query-string and form data.
* **0.26** – Makes sub-application handoff independent of middleware
  ordering, improving reliability for mounted ASGI apps.
* **0.25** – Fixes Unicode redirect handling by percent-encoding
  non-ASCII path segments before writing the ``Location`` header.
* **0.24** – Improves session lifecycle behaviour by expiring stale
  in-memory sessions and deleting persisted sessions when they become
  empty.
* **0.23** – Ensures background multipart parsing stops immediately when a
  request is terminated by middleware, preventing unnecessary resource
  usage.
* **0.22** – Fixes body parsing in mounted sub-applications by sharing
  ``body_params`` and ``body_parsed`` state with the parent request.
* **0.21** – Allows the implicit ``index`` route handler to receive path
  parameters, aligning it with other handlers.
* **0.20** – Introduces concurrent multipart parsing with bounded queues
  so that large uploads do not block other requests.
* **0.19** – Improves debugging via richer tracebacks and adds
  middleware hooks for mounting sub-applications.
* **0.18** – Cancels asynchronous generator handlers when the client
  disconnects to avoid leaking resources during streaming responses.
* **0.17** – Updates the lifespan hook API to match middleware APIs,
  enabling ``app.startup_handlers.append(handler)`` style usage.
* **0.16** – Adds first-class lifespan event support with
  ``on_startup`` and ``on_shutdown`` helpers.
* **0.15** – Hardens optional dependency imports, improving behaviour
  when extras such as ``orjson`` or ``jinja2`` are unavailable.
* **0.14** – Renames the package import to ``micropie`` (breaking change)
  to align module naming with Python conventions.
* **0.13** – Introduces built-in WebSocket support, opening the door to
  real-time applications without additional middleware.

Breaking changes in 0.32
------------------------

Version 0.32 intentionally changes several public behaviours.  Review each
item before upgrading an existing application.

* **Session values no longer bind to handler arguments.** This applies to
  both HTTP and WebSocket handlers.  A parameter such as ``user_id`` must
  come from path, query, form, JSON or file input (as applicable), or have a
  default.  Read trusted state explicitly instead:

  .. code-block:: python

     async def transfer(self, amount):
         user_id = self.request.session["user_id"]
         return await make_transfer(user_id, amount)

* **Request.form() no longer reads JSON bodies.** JSON objects are no longer
  copied into ``Request.body_params``; code using ``request.form(...)`` for
  JSON must move to ``request.json(...)``.  Top-level JSON object keys still
  bind to handler arguments, but values retain their native JSON types instead
  of being converted with ``str()``.  The namespace change also applies to
  middleware and mounted sub-applications that inspect ``body_params``.

* **Session IDs use UUIDv4 validation by default.** Existing non-UUID session
  cookies are rejected, and non-UUID values passed to
  ``WebSocket.accept(session_id=...)`` raise ``ValueError``.  Custom session
  back-ends must configure matching ``session_id_factory`` and
  ``session_id_validator`` callables.  Session IDs also rotate when an empty
  session becomes populated, so clients must honor the returned
  ``Set-Cookie`` header.

* **Request-body limits are enabled by default.** Bodies larger than 16 MiB
  receive ``413 Payload Too Large``.  Each accumulated multipart text field
  is additionally limited to 1 MiB.  Pass larger values—or ``None`` to
  disable a limit—through ``max_body_size`` and ``max_form_field_size`` when
  larger payloads are intentional.

* **Aborted multipart file streams raise an exception.** A file queue yields
  ``None`` only after a complete upload.  Parser failures, idle timeouts and
  size-limit failures now raise :class:`~micropie.MultipartFileError` from
  ``get()``.  Upload consumers must treat that exception as an incomplete
  file and avoid persisting partial data.

* **Python 3.11 or newer is required.** Package metadata now declares the
  framework's actual interpreter requirement, including its use of
  ``asyncio.timeout``.  Installers will reject older Python versions instead
  of installing a package that cannot run correctly.

* **Some error and middleware values are normalized.** JSON response bodies
  passed to ``HttpMiddleware.after_request`` are now text regardless of
  whether ``orjson`` is installed.  Unhandled WebSocket handler exceptions
  close with code ``1011`` and the generic reason ``Internal server error``;
  exception details are available only through server logging.

Upgrade tips
------------

* **URL-encoded parsing remains permissive.** Query strings and URL-encoded
  form bodies retain their earlier behavior: empty and bare fields are omitted
  and malformed encoding is tolerated.
* **Check optional extras.** When upgrading, confirm that any optional
  dependencies you rely on (``jinja2``, ``multipart``, ``orjson``) are
  still installed, especially if you pin minimal environments.
* **Review lifespan handlers.** Releases 0.16 and 0.17 reshape the
  startup/shutdown API. Adjust custom startup hooks to use the new
  ``app.startup_handlers`` and ``app.shutdown_handlers`` lists.
* **Validate redirects with non-ASCII paths.** If your app builds
  redirect targets dynamically, verify behaviour after 0.25 where
  redirect paths are safely encoded for ASGI header transport.
* **Audit long-lived streams.** If you emit server-sent events or
  streaming responses, ensure your handlers handle cancellation so the
  0.18 change does not mask cleanup bugs.
* **Evaluate mounted applications.** If you mount other ASGI apps using
  middleware, upgrade to at least 0.22 for body parsing fixes and to
  0.26 for middleware-ordering-safe sub-application routing.

Looking for more?
-----------------

The :mod:`micropie` source distribution ships a ``docs/release_notes.md``
file with the raw changelog. You can also browse historical discussions
and pull requests on the project's `GitHub repository <https://github.com/patx/micropie>`_.
