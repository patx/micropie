import threading
import asyncio
import websockets
from MicroPie import Server

class MyApp(Server):
    def index(self):
        return "WebSocket available at ws://localhost:8765"

def start_websocket_server():
    async def echo(websocket, path):
        async for message in websocket:
            await websocket.send(f"Echo: {message}")

    asyncio.run(websockets.serve(echo, "localhost", 8765))
    asyncio.get_event_loop().run_forever()

# Run MicroPie in the main thread
if __name__ == "__main__":
    threading.Thread(target=start_websocket_server, daemon=True).start()
    MyApp().run()
