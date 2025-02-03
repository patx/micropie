import socketio
from MicroPie import App

# Create a Socket.IO server with CORS support
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")  # Allow all origins

# Create the MicroPie server
class MyApp(App):
    async def index(self):
        return await self._render_template("chat.html")

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
app = socketio.ASGIApp(sio, asgi_app)
