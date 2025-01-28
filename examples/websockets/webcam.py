from typing import Dict, Set, Any
from MicroPie import Server

# Keep track of active users (who have "started streaming")
active_users: Set[str] = set()
streamers: Dict[str, Set[Any]] = {}
watchers: Dict[str, Set[Any]] = {}

class MyApp(Server):

    async def index(self):
        return self.render_template("index_stream.html")

    async def submit(self, username: str, action: str):
        if username:
            active_users.add(username)
            route = f"/stream/{username}" if action == "Start Streaming" else f"/watch/{username}"
            return self.redirect(route)
        return self.redirect("/")

    async def stream(self, username: str):
        return self.render_template("stream.html", username=username) if username in active_users else self.redirect("/")

    async def watch(self, username: str):
        return self.render_template("watch.html", username=username) if username in active_users else self.redirect("/")

    async def websocket_stream(self, scope, receive, send):
        username = self.path_params[0] if self.path_params else None
        if not username or username not in active_users:
            return await self._reject_websocket(send)

        await send({"type": "websocket.accept"})
        streamers.setdefault(username, set()).add(send)

        await self._handle_websocket(receive, send, username, streamers, is_stream=True)

    async def websocket_watch(self, scope, receive, send):
        username = self.path_params[0] if self.path_params else None
        if not username or username not in active_users:
            return await self._reject_websocket(send)

        await send({"type": "websocket.accept"})
        watchers.setdefault(username, set()).add(send)

        await self._handle_websocket(receive, send, username, watchers)

    async def _handle_websocket(self, receive, send, username, registry, is_stream=False):
        try:
            while True:
                message = await receive()
                if message["type"] == "websocket.receive":
                    if "text" in message or "bytes" in message:
                        await self._broadcast(username, message.get("text") or message.get("bytes"), is_binary="bytes" in message)
                elif message["type"] == "websocket.disconnect":
                    break
        finally:
            registry[username].discard(send)
            if not registry[username]:
                del registry[username]

    async def _reject_websocket(self, send):
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 4000})

    async def _broadcast(self, username: str, data, is_binary: bool = False):
        for ws_send in list(watchers.get(username, [])):
            try:
                await ws_send({"type": "websocket.send", "bytes" if is_binary else "text": data})
            except:
                watchers[username].discard(ws_send)
                if not watchers[username]:
                    del watchers[username]

# Create the ASGI app
app = MyApp()
