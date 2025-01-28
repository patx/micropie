import uvicorn
from typing import Dict, Set, Any

from MicroPie import AsyncServer

# Keep track of active users (who have "started streaming")
active_users = set()

# A simple in-memory registry of connected WebSocket clients:
# For each username, we store sets of WebSocket connections:
streamers: Dict[str, Set[Any]] = {}
watchers: Dict[str, Set[Any]] = {}


class MyApp(AsyncServer):

    async def index(self):
        """Show the home page with form to either start or watch stream."""
        return self.render_template("index.html")

    async def submit(self, username, action):
        """
        Handle the form submission from 'index.html'.
        Allows user to pick 'Start Streaming' or 'Watch Stream'.
        """
        if username:
            active_users.add(username)
            if action == "Start Streaming":
                return self.redirect(f"/stream/{username}")
            elif action == "Watch Stream":
                return self.redirect(f"/watch/{username}")
        return self.redirect("/")

    async def stream(self, username):
        """
        Show the streaming page for a particular username.
        Only valid if the username is in active_users.
        """
        if username not in active_users:
            return self.redirect("/")
        return self.render_template("stream.html", username=username)

    async def watch(self, username):
        """
        Show the watch page for a particular username.
        Only valid if the username is in active_users.
        """
        if username not in active_users:
            return self.redirect("/")
        return self.render_template("watch.html", username=username)

    #
    # WebSocket routes
    #
    async def websocket_stream(self, scope, receive, send):
        """
        Handle WebSocket connections for a streamer, i.e. /stream/<username>.
        Path params: [username]
        """
        # We expect self.path_params[0] to be the username.
        if not self.path_params:
            await self._reject_websocket(send)
            return

        username = self.path_params[0]
        if username not in active_users:
            await self._reject_websocket(send)
            return

        # Accept the WebSocket connection
        await send({"type": "websocket.accept"})

        # Ensure we have a set for this username
        if username not in streamers:
            streamers[username] = set()
        streamers[username].add(send)

        try:
            while True:
                message = await receive()
                if message["type"] == "websocket.receive":
                    # We expect JSON or text frames. If binary, adapt as needed.
                    # For a simple approach, let's assume 'text' with a JSON-like structure
                    # or a raw image frame in 'bytes'.
                    if "text" in message:
                        text_data = message["text"]
                        # Broadcast text_data to watchers of this username
                        await self._broadcast(username, text_data)
                    elif "bytes" in message:
                        binary_frame = message["bytes"]
                        # Broadcast binary frame to watchers of this username
                        await self._broadcast(username, binary_frame, is_binary=True)
                elif message["type"] == "websocket.disconnect":
                    break
        finally:
            # On disconnect, remove this send channel from the streamer set
            streamers[username].discard(send)
            if not streamers[username]:
                del streamers[username]

    async def websocket_watch(self, scope, receive, send):
        """
        Handle WebSocket connections for watchers, i.e. /watch/<username>.
        Path params: [username]
        """
        # We expect self.path_params[0] to be the username.
        if not self.path_params:
            await self._reject_websocket(send)
            return

        username = self.path_params[0]
        if username not in active_users:
            await self._reject_websocket(send)
            return

        # Accept the WebSocket connection
        await send({"type": "websocket.accept"})

        # Ensure we have a set for watchers of this username
        if username not in watchers:
            watchers[username] = set()
        watchers[username].add(send)

        try:
            while True:
                message = await receive()
                # Typically watchers won't send frames, but you could handle
                # text commands from watchers if needed.
                if message["type"] == "websocket.disconnect":
                    break
        finally:
            # On disconnect, remove this send channel from the watchers set
            watchers[username].discard(send)
            if not watchers[username]:
                del watchers[username]

    #
    # Helper methods
    #
    async def _reject_websocket(self, send):
        """Reject a WebSocket connection (invalid user or path)."""
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 4000})

    async def _broadcast(self, username: str, data, is_binary: bool = False):
        """
        Broadcast a message to all watchers of the specified username.
        data can be str or bytes. is_binary toggles send mode.
        """
        if username not in watchers:
            return
        for ws_send in list(watchers[username]):
            try:
                if is_binary:
                    await ws_send({"type": "websocket.send", "bytes": data})
                else:
                    await ws_send({"type": "websocket.send", "text": data})
            except:
                # If we fail to send, assume the connection is dead
                watchers[username].discard(ws_send)
                if not watchers[username]:
                    del watchers[username]


# Create our application instance
app = MyApp()

#
# If you want to run directly from python (instead of `uvicorn myapp:app`), do:
#
if __name__ == "__main__":
    uvicorn.run("myapp:app", host="0.0.0.0", port=5000, reload=True)

