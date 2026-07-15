[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## Releases Notes
- **[0.32](https://github.com/patx/micropie/releases/tag/v0.32)** - Harden request parsing, multipart streaming, sessions, parameter binding, logging, and response streaming. URL-encoded query and form parsing remain permissive and compatible with earlier releases.
  - **Breaking — session binding:** HTTP and WebSocket handler arguments are no longer populated from session data. Read trusted state explicitly from `self.request.session`.
  - **Breaking — `Request.form()` and JSON:** `Request.form()` no longer returns values from JSON bodies because JSON objects are no longer mirrored into `body_params`. Use `request.json(...)` instead. Top-level JSON keys still bind to handler arguments, now with native JSON types.
  - **Breaking — session IDs:** Session cookies and explicit `WebSocket.accept(session_id=...)` values use canonical UUIDv4 validation by default. Custom backends must configure matching `session_id_factory` and `session_id_validator` callables; otherwise existing non-UUID sessions are rejected.
  - **Breaking — request limits:** Requests now default to a 16 MiB total body limit and multipart text fields to 1 MiB. Configure larger values or `None` when an application intentionally accepts more.
  - **Breaking — multipart failures:** An aborted upload now raises `MultipartFileError` from the file queue instead of yielding a clean `None` sentinel. Treat `None` as successful EOF and handle the exception as an incomplete upload.
  - **Breaking — Python requirement:** Package metadata now requires Python 3.11 or newer, matching the framework's use of Python 3.11 asyncio APIs. Older interpreters are no longer accepted by installers.
  - **Integration changes:** JSON response bodies passed to HTTP middleware are consistently text even when `orjson` is installed, and unhandled WebSocket handler failures now use a generic `1011` close reason while logging details server-side.
- **[0.31](https://github.com/patx/micropie/releases/tag/v0.31)** - Security fix: route lookup now ignores non-callable public attributes and property-like descriptors, preventing internal App attributes from being treated as handlers while preserving descriptor-backed route methods.
- **[0.30](https://github.com/patx/micropie/releases/tag/v0.30)** - Remove the public `Request.get_json` attribute. Use `Request.json()` or `Request.json(name, default)`.
- **[0.29](https://github.com/patx/micropie/releases/tag/v0.29)** - Performance upgrades, no more per request signature inspections for routing. 24%-54% increase in req/sec.
- **[0.28](https://github.com/patx/micropie/releases/tag/v0.28)** - Add `Request.json` helper
- **[0.27](https://github.com/patx/micropie/releases/tag/v0.27)** - Add `Request.query` and `Request.form` helpers
- **[0.26](https://github.com/patx/micropie/releases/tag/v0.26)** - Sub-app routing no longer depends on middleware ordering
- **[0.25](https://github.com/patx/micropie/releases/tag/v0.25)** - Fix unicode redirect handling. Percent-encode non-ASCII path segments before setting Location header. Prevents latin-1 header encoding errors and avoids double-encoding queries.
- **[0.24](https://github.com/patx/micropie/releases/tag/v0.24)** - Improve session handling. Expired sessions now clean up properly, and empty sessions delete stored data. Session saving also moved after `after_request` middleware.
- **[0.23](https://github.com/patx/micropie/releases/tag/v0.23)** - Bug fix release. Make sure background multipart parsing stops when the request is terminated by middleware
- **[0.22](https://github.com/patx/micropie/releases/tag/v0.22)** - Bug fix release. Fix sub-app body parsing bug by ensuring `Request` object inherits scope's `body_params` and `body_parsed`, preventing redundant parsing in sub-app
- **[0.21](https://github.com/patx/micropie/releases/tag/v0.21)** - Bug fix release. Make sure index route handler can handle path params
- **[0.20](https://github.com/patx/micropie/releases/tag/v0.20)** - Enable concurrent multipart parsing and file writing with bounded queues
- **[0.19](https://github.com/patx/micropie/releases/tag/v0.19)** - Easier debugging with `traceback`. Add `_sub_app` attribute to allow middleware to mount other ASGI applications
- **[0.18](https://github.com/patx/micropie/releases/tag/v0.18)** - Ensure handlers that return async generators are killed upon client disconnect to prevent memory leaks
- **[0.17](https://github.com/patx/micropie/releases/tag/v0.17)** - Change API of lifespan events to match API of middlewaress, eg. `app.startup_handlers.append(handler)`
- **[0.16](https://github.com/patx/micropie/releases/tag/v0.16)** - Add support for lifespan events using `on_startup` and `on_shutdown`
- **[0.15](https://github.com/patx/micropie/releases/tag/v0.15)** - Minor bug fixes in the optional dependencies if statements
- **[0.14](https://github.com/patx/micropie/releases/tag/v0.14)** - Change import to `micropie` instead of `MicroPie` **BREAKING CHANGE**
- **[0.13](https://github.com/patx/micropie/releases/tag/v0.13)** - Introduce built-in WebSocket support

All releases since 0.13 will be listed here. For older releases see [tags on Github](https://github.com/patx/micropie/tags)
