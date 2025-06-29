from micropie import App, ConnectionClosed

class MyApp(App):
    async def chat(self):
        """HTTP handler for GET /chat"""
        return "Welcome to MicroPie, this is an HTTP GET route!"

    async def ws_chat(self, ws, room=None):
        """WebSocket handler for ws://localhost:8000/chat"""
        await ws.accept()
        user = self.request.query_params.get("user", ["anonymous"])[0]
        self.request.session["last_room"] = room or "default"
        while True:
            try:
                message = await ws.receive_text()
                response = f"{user} in {room or 'default'}: {message}"
                await ws.send_text(response)
            except ConnectionClosed:
                break

app = MyApp()
