from typing import Dict, Set, Any
from MicroPie import Server

# We track who is "active" (registered a username)
active_users: Set[str] = set()

# We store a dictionary of channels -> sets of websocket send handles
# For a single chat room, we only need one channel, e.g. "global".
watchers: Dict[str, Set[Any]] = {}

class ChatApp(Server):
    async def index(self):
        """
        Serve a simple form where the user enters a username.
        """
        return self.render_template("index_chat.html")

    async def submit(self, username: str):
        """
        Handle the POST from index.html where user enters their name.
        Then redirect them to /chat/<username>.
        """
        username = username.strip()
        if not username:
            return self.redirect("/")  # Invalid username, go back

        # Mark this user as active
        active_users.add(username)
        return self.redirect(f"/chat/{username}")

    async def chat(self, username: str):
        """
        Show the chat page if the user is active; otherwise, redirect home.
        """
        if username not in active_users:
            return self.redirect("/")
        return self.render_template("chat.html", username=username)

    #
    # ------------- WEBSOCKET HANDLER -------------
    #
    async def websocket_chat(self, scope, receive, send):
        """
        If the path is /chat/<username>, MicroPie calls this method
        because 'websocket_{pathParts[0]}' = 'websocket_chat'.
        """
        # Extract the <username> from self.path_params
        username = self.path_params[0] if self.path_params else None

        # 1) Make sure username is valid and active
        if not username or username not in active_users:
            return await self._reject_websocket(send)

        # 2) Wait for 'websocket.connect' before accepting
        msg = await receive()
        if msg["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})
        else:
            # If we didn’t get the connect message, close
            return await self._reject_websocket(send)

        # 3) Add this connection to watchers["global"]
        watchers.setdefault("global", set()).add(send)

        # 4) Handle incoming messages until the client disconnects
        try:
            while True:
                message = await receive()
                if message["type"] == "websocket.receive":
                    # If there's text, broadcast it
                    if "text" in message:
                        text_msg = message["text"]
                        await self._broadcast("global", f"{username}: {text_msg}", is_binary=False)
                    elif "bytes" in message:
                        byte_data = message["bytes"]
                        await self._broadcast("global", byte_data, is_binary=True)
                elif message["type"] == "websocket.disconnect":
                    break
        finally:
            # Remove the user's send handle from watchers["global"]
            watchers["global"].discard(send)
            # If watchers["global"] is empty, remove the channel
            if not watchers["global"]:
                del watchers["global"]

    #
    # ------------- HELPER METHODS -------------
    #
    async def _reject_websocket(self, send):
        """
        Accept then immediately close with a custom code.
        This is a simple approach to gracefully reject a WebSocket.
        """
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 4000})

    async def _broadcast(self, channel: str, data, is_binary: bool = False):
        """
        Broadcast 'data' to all watchers in the given channel.
        """
        for ws_send in list(watchers.get(channel, [])):
            try:
                await ws_send({
                    "type": "websocket.send",
                    "bytes" if is_binary else "text": data
                })
            except:
                # If sending fails, remove that watcher's socket
                watchers[channel].discard(ws_send)
                if not watchers[channel]:
                    del watchers[channel]

# Create the ASGI app instance
app = ChatApp()

# If you want to run via uvicorn:
#   uvicorn chat_app:app --host 127.0.0.1 --port 5000

