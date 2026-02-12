[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

[MicroPie](https://patx.github.io/micropie) is an ultra-micro ASGI Python web framework for building fast, async web apps with minimal boilerplate. It includes convention-based routing, sessions, middleware, WebSocket support, lifespan hooks, and optional template rendering.

## Quick Start
```python
from micropie import App

class MyApp(App):
    async def index(self):
        return "Hello, MicroPie!"

app = MyApp()  # Run with `uvicorn app:app`
```

Run:

```bash
uvicorn app:app
```

## Installation

```bash
$ pip install micropie[standard]
```

Other profiles:

```bash
$ pip install micropie          # minimal
$ pip install micropie[all]     # standard + orjson + uvicorn
```

## Useful Links
- **Homepage**: [patx.github.io/micropie](https://patx.github.io/micropie)
- **Official Documentation**: [micropie.readthedocs.io](https://micropie.readthedocs.io/)
- **PyPI Page**: [pypi.org/project/MicroPie](https://pypi.org/project/MicroPie/)
- **GitHub Project**: [github.com/patx/micropie](https://github.com/patx/micropie)
- **Examples**: [github.com/patx/micropie/tree/main/examples](https://github.com/patx/micropie/tree/main/examples)

