from micropie_routing import ExplicitApp, route, ws_route
from micropie import WebSocket, ConnectionClosed

class MyApp(ExplicitApp):
    @route("/api/users/{user_id:int}", method=["GET"])
    async def get_user(self, user_id: int):
        return f"User ID: {user_id}"

    @ws_route("/ws/chat/{room:str}")
    async def ws_chat(self, ws: WebSocket, room: str):
        await ws.accept()
        user = self.request.query_params.get("user", ["anonymous"])[0]
        self.request.session["last_room"] = room
        while True:
            try:
                message = await ws.receive_text()
                response = f"{user} ({room}): {message}"
                await ws.send_text(response)
            except ConnectionClosed:
                break

app = MyApp()
