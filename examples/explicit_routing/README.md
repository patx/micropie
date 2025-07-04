## Explicit Routing with MicroPie

MicroPie now supports explicit routing through the `ExplicitApp` class, `route` and `ws_route` decorators, and router middleware. This allows you to define routes declaratively with type-safe parameters and debug them easily.

### Key Features
- **Decorators**: Use `@route` for HTTP and `@ws_route` for WebSocket routes.
- **Type-Safe Parameters**: Support for `int`, `str`, `float`, and `uuid` in path parameters (e.g., `/users/{user}/{age:int}`).
- **Debugging**: Use `app.list_routes()` to inspect registered routes.
- **Validation**: HTTP methods and path formats are validated at decoration time.
- **Subprotocols**: WebSocket routes support optional subprotocols.

### Example Usage

#### HTTP Routing
```python
from micropie_routing import ExplicitApp, route

class MyApp(ExplicitApp):
    @route("/greet/{name}", method=["GET", "POST"])
    async def greet(self, name: str = "Guest"):
        return f"Hello, {name}!"

    @route("/user/{id:int}", method="GET")
    async def get_user(self, id: int):
        return {"user_id": id}

app = MyApp()
print(app.list_routes())  # Debug routes
```

**Access:**
- `GET /greet/Alice` → `"Hello, Alice!"`
- `GET /user/123` → `{"user_id": 123}`

#### WebSocket Routing
```python
from micropie_routing import ExplicitApp, ws_route
from micropie import WebSocket

class MyApp(ExplicitApp):
    @ws_route("/ws/chat/{room}")
    async def ws_chat(self, ws: WebSocket, room: str):
        await ws.accept()
        while True:
            msg = await ws.receive_text()
            await ws.send_text(f"Room {room}: {msg}")

app = MyApp()
```

**Connect:**
- `ws://127.0.0.1:8000/ws/chat/lobby` → Echoes messages with room prefix.

### Debugging Routes
Use `app.list_routes()` to inspect registered routes:
```python
print(app.list_routes())
```
Output:
```json
{
    "http": [
        {"path": "/greet/{name}", "methods_or_subprotocol": ["GET", "POST"], "handler": "greet"},
        {"path": "/user/{id:int}", "methods_or_subprotocol": ["GET"], "handler": "get_user"}
    ],
    "websocket": [
        {"path": "/ws/chat/{room}", "methods_or_subprotocol": null, "handler": "ws_chat"}
    ]
}
```

### Notes
- **Path Syntax**: Use `{name}` for strings or `{name:type}` for `int`, `float`, or `uuid`.
- **Validation**: Invalid HTTP methods or paths raise `InvalidMethodError` or `InvalidPathError` at decoration time.
- **Performance**: Regex patterns are pre-compiled for faster matching.

Check the [examples/explicit_routing](https://github.com/patx/micropie/tree/main/examples/explicit_routing) folder for more advanced usage.
