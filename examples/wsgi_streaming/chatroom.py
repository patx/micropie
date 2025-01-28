import asyncio
import websockets
import multiprocessing
from MicroPie import Server

# Store connected WebSocket clients
connected_clients = set()

class MyApp(Server):
    def index(self):
        return """
        <html>
        <head>
            <script>
                var ws = new WebSocket("ws://localhost:8765");
                ws.onopen = function() {
                    console.log("Connected to WebSocket server");
                };
                ws.onmessage = function(event) {
                    document.getElementById("output").innerHTML += event.data + "<br>";
                };
                function sendMessage() {
                    var message = document.getElementById("message").value;
                    ws.send(message);
                    document.getElementById("message").value = "";  // Clear input after sending
                }
                window.onbeforeunload = function() {
                    ws.close();
                };
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
    """Handles incoming WebSocket connections and broadcasts messages to all clients."""
    global connected_clients
    connected_clients.add(websocket)
    print("Client connected")

    try:
        async for message in websocket:
            print(f"Received: {message}")
            response = f"User: {message}"
            await broadcast(response)  # Send to all connected clients
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    finally:
        connected_clients.remove(websocket)

async def broadcast(message):
    """Send a message to all connected WebSocket clients."""
    if connected_clients:
        await asyncio.wait([client.send(message) for client in connected_clients])

async def websocket_server():
    """Start the WebSocket server within the asyncio event loop."""
    async with websockets.serve(websocket_handler, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # Keep the server running indefinitely

def start_websocket_server():
    """Runs the WebSocket server with asyncio.run() in a separate thread."""
    asyncio.run(websocket_server())

app = MyApp()


if __name__ == "__main__":
    import threading

    # Start the WebSocket server in a separate thread
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()

    print("WebSocket server running on ws://localhost:8765")

    # Start the Gunicorn server in a separate process
    wsgi_process = multiprocessing.Process(target=app.run())
    wsgi_process.start()

    wsgi_process.join()  # Keep the main process alive

