import socketio
from MicroPie import Server

# Create a Socket.IO server with CORS support
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")  # Allow all origins

# Create the MicroPie server
class MyApp(Server):
    def index(self):
        return """
        <html>
        <head>
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
            <script>
                var socket = io("http://localhost:8000");
                socket.on("connect", function() {
                    console.log("Connected to Socket.IO server");
                });
                socket.on("message", function(data) {
                    document.getElementById("output").innerHTML += data + "<br>";
                });
                function sendMessage() {
                    var message = document.getElementById("message").value;
                    socket.send(message);
                    document.getElementById("message").value = "";  // Clear input after sending
                }
                window.onbeforeunload = function() {
                    socket.disconnect();
                };
            </script>
        </head>
        <body>
            <h1>Socket.IO Chat</h1>
            <input type="text" id="message" placeholder="Type a message">
            <button onclick="sendMessage()">Send</button>
            <div id="output"></div>
        </body>
        </html>
        """

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def message(sid, data):
    print(f"Received message from {sid}: {data}")
    # Broadcast the message to all connected clients
    await sio.emit("message", f"User: {data}", room=None)



# Attach Socket.IO to the ASGI app
asgi_app = MyApp()
app = socketio.ASGIApp(sio, app)
