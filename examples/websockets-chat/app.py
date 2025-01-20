import asyncio
import websockets
from MicroPie import Server

class MyApp(Server):
    def index(self):
        return """
        <html>
        <head>
            <script>
                var ws = new WebSocket("ws://localhost:8765");
                ws.onmessage = function(event) {
                    document.getElementById("output").innerHTML += event.data + "<br>";
                };
                function sendMessage() {
                    var message = document.getElementById("message").value;
                    ws.send(message);
                }
            </script>
        </head>
        <body>
            <h1>WebSocket Chat</h1>
            <input type="text" id="message" placeholder="Type a message">
            <button onclick="sendMessage()">Send</button>
            <div id="output"></div>
        </body>
        </html>
        """

async def websocket_handler(websocket):
    """Handles incoming WebSocket connections"""
    print("Client connected")
    try:
        async for message in websocket:
            print(f"Received: {message}")
            response = f"Echo: {message}"
            await websocket.send(response)
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def websocket_server():
    """Start WebSocket server within the asyncio event loop"""
    async with websockets.serve(websocket_handler, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # Keep the server running indefinitely

def start_websocket_server():
    """Runs the WebSocket server with asyncio.run() in a separate thread"""
    asyncio.run(websocket_server())

if __name__ == "__main__":
    import threading

    # Start the WebSocket server in a separate thread
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()

    # Start the MicroPie server
    MyApp().run()

