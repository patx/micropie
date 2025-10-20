.. MicroPie documentation master file, created for the MicroPie ASGI framework.

MicroPie ASGI Web Framework
===========================

MicroPie is a small, asynchronous web framework built on top of the
ASGI specification.  It is designed to be simple to learn and easy to
extend while still providing the features necessary to build modern web
applications.  MicroPie offers automatic URL routing, pluggable
session back‑ends, middleware hooks, WebSocket support and optional
template rendering.  Its focus on minimalism makes it a good choice for
lightweight services, APIs and educational projects.

Core features
-------------

* **Convention over configuration.** Public methods on your
  :class:`~micropie.App` subclass automatically become routes so you can
  ship a prototype with only a handful of lines of code.
* **Async‑first request handling.** MicroPie speaks ASGI fluently and
  embraces ``async``/``await`` for HTTP and WebSocket handlers while
  keeping synchronous handlers ergonomic.
* **Built‑in sessions and middleware.** A pluggable session backend and
  request/response middleware hooks make it easy to add authentication,
  analytics and other cross‑cutting concerns.
* **Optional batteries included.** Extras for templating, fast JSON and
  multipart parsing allow you to scale capabilities without bloating the
  core package.

Learning path
-------------

New to MicroPie? Follow this recommended progression:

1. :doc:`tutorial/quickstart` – install the framework and serve your
   first response.
2. :doc:`tutorial/routing` – understand how method names map to URL
   paths and how handler arguments are populated.
3. :doc:`tutorial/websockets` – build a live, bidirectional endpoint.
4. :doc:`howto/index` – explore recipes for common tasks like sessions,
   templating and streaming.
5. :doc:`reference/index` – deep dive into class and function
   definitions when you need the authoritative contract.
6. :doc:`explanation/index` – read about the philosophy behind the
   design to better understand trade‑offs and extension points.

This documentation is organized according to the
Diátaxis documentation framework. That framework separates documentation into
four distinct types:

* **Tutorials** – step‑by‑step introductions that teach you how to
  accomplish a task.  Tutorials should avoid deep explanations and help
  you get started quickly.
* **How‑to guides** – recipes focused on solving a particular problem.
  Guides assume you already know the basics and want to apply MicroPie
  to a concrete task.
* **Reference** – authoritative descriptions of classes, functions and
  modules.  These documents are factual and concise.
* **Explanation** – discussions that explore the rationale behind
  design choices and deeper concepts in MicroPie.

In addition to these four types, a small glossary collects terminology
used throughout the framework.  Quick links to other helpful resources:

* :doc:`glossary` – definitions of common MicroPie and ASGI terms.
* :doc:`whats_new` – highlights from recent releases and upgrade tips.
* `Project README <https://github.com/patx/micropie#readme>`_ – the
  high-level project overview from the source repository.

.. _Diátaxis documentation framework: https://diataxis.fr/

Contents
========

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   tutorial/index
   howto/index
   reference/index
   explanation/index
   whats_new
   glossary

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
