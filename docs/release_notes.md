[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

## Releases Notes
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
