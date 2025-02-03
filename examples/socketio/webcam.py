import socketio
from MicroPie import App

# Create the Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi")

# Track active users and their watchers/streamers
active_users = set()

# MicroPie Server with integrated Socket.IO
class MyApp(App):
    async def index(self):
        return await self.render_template("index_stream.html")

    async def submit(self, username: str, action: str):
        if username:
            active_users.add(username)
            route = f"/stream/{username}" if action == "Start Streaming" else f"/watch/{username}"
            return self.redirect(route)
        return self.redirect("/")

    async def stream(self, username: str):
        return await self.render_template("stream.html", username=username) if username in active_users else self.redirect("/")

    async def watch(self, username: str):
        return await self.render_template("watch.html", username=username) if username in active_users else self.redirect("/")

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.on("stream_frame")
async def handle_stream_frame(sid, data):
    """
    Broadcast the streamed frame (binary blob) to all watchers.
    data = { "username": <str>, "frame": <binary blob> }
    """
    username = data.get("username")
    frame = data.get("frame")  # This is binary
    if username in active_users:
        # Emit the frame to watchers in username's room
        await sio.emit(
            "video_frame",
            {"username": username, "frame": frame},
            room=username,
        )

@sio.on("join_room")
async def join_room(sid, data):
    """Add a client to a room (either as a streamer or watcher)."""
    username = data.get("username")
    if username in active_users:
        await sio.enter_room(sid, username)  # Await the method
        print(f"{sid} joined room for {username}")

@sio.on("leave_room")
async def leave_room(sid, data):
    """Remove a client from a room."""
    username = data.get("username")
    if username in active_users:
        sio.leave_room(sid, username)
        print(f"{sid} left room for {username}")

# Attach the Socket.IO server to the ASGI app
asgi_app = MyApp()
app = socketio.ASGIApp(sio, asgi_app)
