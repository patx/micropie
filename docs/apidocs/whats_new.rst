.. _release-notes:

What's new in MicroPie
======================

This page summarises noteworthy changes in recent MicroPie releases. It
is not an exhaustive changelog, but it highlights the features and bug
fixes most likely to affect application developers. For the full list of
releases, consult the `GitHub releases page <https://github.com/patx/micropie/releases>`_.

Version highlights
------------------

* **0.23** – Ensures background multipart parsing stops immediately when a
  request is terminated by middleware, preventing unnecessary resource
  usage.
* **0.22** – Fixes body parsing in mounted sub-applications by sharing
  ``body_params`` and ``body_parsed`` state with the parent request.
* **0.21** – Allows the implicit ``index`` route handler to receive path
  parameters, aligning it with other handlers.
* **0.20** – Introduces concurrent multipart parsing with bounded queues
  so that large uploads do not block other requests.
* **0.19** – Improves debugging via richer tracebacks and adds the
  ``_sub_app`` attribute for mounting other ASGI applications.
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

Upgrade tips
------------

* **Check optional extras.** When upgrading, confirm that any optional
  dependencies you rely on (``jinja2``, ``multipart``, ``orjson``) are
  still installed, especially if you pin minimal environments.
* **Review lifespan handlers.** Releases 0.16 and 0.17 reshape the
  startup/shutdown API. Adjust custom startup hooks to use the new
  ``app.startup_handlers`` and ``app.shutdown_handlers`` lists.
* **Audit long-lived streams.** If you emit server-sent events or
  streaming responses, ensure your handlers handle cancellation so the
  0.18 change does not mask cleanup bugs.
* **Evaluate mounted applications.** If you mount other ASGI apps using
  middleware, upgrade to at least 0.19 to benefit from the ``_sub_app``
  attribute and the body parsing fixes introduced in 0.22.

Looking for more?
-----------------

The :mod:`micropie` source distribution ships a ``docs/release_notes.md``
file with the raw changelog. You can also browse historical discussions
and pull requests on the project's `GitHub repository <https://github.com/patx/micropie>`_.
