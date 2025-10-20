Design philosophy
=================

Understanding MicroPie's guiding principles makes it easier to decide
whether the framework fits your project and how to extend it without
fighting the grain. This page complements the
:doc:`architecture <architecture>` overview by focusing on the trade-offs
behind key decisions.

Keep the core tiny
------------------

MicroPie prefers explicit, readable Python over layers of abstraction.
The entire framework fits in a single module so you can audit its
behaviour quickly. Features graduate into the core only if they pull
their weight for the majority of applications. Everything else—ORMs,
background workers, dependency injection—remains a userland concern.

Route by convention, customise with middleware
----------------------------------------------

Automatic route discovery lowers the barrier to entry: write a method,
get an endpoint. The flip side is that large applications sometimes need
more deliberate routing. Instead of complicating the core dispatcher,
MicroPie encourages you to plug in :class:`~micropie.HttpMiddleware`
that rewrites the request target or delegates to sub-apps. This keeps the
framework flexible without sacrificing the quick-start experience.

Treat async as the default
--------------------------

ASGI enables concurrency, so MicroPie leans into ``async``/``await`` at
every layer. Synchronous handlers are supported for convenience, but the
internal plumbing always assumes asynchronous execution. Middleware and
session backends follow the same rule. When you need to integrate a
blocking library, run it in a thread pool explicitly so the framework
stays responsive.

Design for graceful degradation
-------------------------------

Optional dependencies such as ``jinja2``, ``multipart`` and ``orjson``
are detected at runtime. If they are missing, MicroPie falls back to
standard-library implementations. This approach keeps installation
friction low for small services while allowing power users to opt in to
richer features.

Favour composition over special cases
-------------------------------------

Rather than adding bespoke APIs for every scenario, MicroPie exposes a
few flexible hooks:

* Context variables keep the current request accessible without global
  state.
* Middleware runs before and after handlers for both HTTP and WebSocket
  flows.
* Session backends are swappable classes with a small, well-documented
  interface.

By composing these building blocks you can implement authentication,
logging, rate limiting and other behaviours without touching the core.

Balance ergonomics with transparency
------------------------------------

MicroPie does not hide the ASGI protocol. Request and WebSocket objects
mirror the underlying scope so you can drop to the metal when required.
At the same time, helper methods normalise headers, cookies and body
parsing. The goal is to keep magic to a minimum while smoothing common
operations.

Where to go next
----------------

* Revisit the :doc:`tutorials <../tutorial/index>` with the design goals
  in mind to see how they shape the developer experience.
* Browse ``tests.py`` to understand the expected behaviour of each hook.
* If you plan to extend MicroPie, read the
  :doc:`reference/index` to learn the public APIs you can rely on.
