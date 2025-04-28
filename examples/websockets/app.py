from MicroPie import App, WebSocket
from typing import List

class MyApp(App):
    def __init__(self):
        super().__init__()
        # Store active WebSocket connections
        self.active_connections: List[WebSocket] = []

    async def index(self):
        """Render the chat HTML page."""
        return await self._render_template("chat.html")

    async def chat(self):
        """Render the chat HTML page for /chat."""
        return await self._render_template("chat.html")

    async def ws_chat(self, websocket: WebSocket, path_params: List[str]):
        """Handle WebSocket connections for the chat."""
        try:
            # Accept the WebSocket connection
            await websocket.accept()
            print(f"Client connected: {id(websocket)}")

            # Add to active connections
            self.active_connections.append(websocket)

            # Main WebSocket loop
            while True:
                # Receive messages
                message = await websocket.receive_text()
                print(f"Received message: {message}")

                # Broadcast the message to all connected clients
                for conn in self.active_connections:
                    await conn.send_text(f"User: {message}")

        except ConnectionError:
            print(f"Client disconnected: {id(websocket)}")
        finally:
            # Remove from active connections and close
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            await websocket.close()

app = MyApp()
