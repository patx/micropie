import socketio
from MicroPie import App
from kenobi import KenobiDB
from datetime import datetime
import asyncio

# KenobiDB setup
db = KenobiDB("chat.db")

# Create a Socket.IO server with CORS support
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Store connected users
connected_users = {}

# Create the MicroPie server
class MyApp(App):
    async def index(self):
        return await self._render_template("chat.html")

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    # Add user with temporary username
    connected_users[sid] = f"User_{sid[:4]}"
    await update_user_list()
    
    # Send recent messages to the newly connected client
    recent_messages = db.search("type", "message", limit=50)
    for msg in recent_messages:
        await sio.emit('message', {
            'username': msg['username'],
            'message': msg['message'],
            'timestamp': msg['timestamp']
        }, room=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Remove user from connected users
    if sid in connected_users:
        del connected_users[sid]
    await update_user_list()

@sio.event
async def set_username(sid, data):
    """Handle username setting"""
    username = data.get('username', '').strip()
    if username and len(username) <= 20:  # Basic validation
        if username in connected_users.values():
            await sio.emit('error', {'message': 'Invalid username'}, room=sid)
        connected_users[sid] = username
        print(f"User {sid} set username to {username}")
        await update_user_list()
    else:
        await sio.emit('error', {'message': 'Invalid username'}, room=sid)

@sio.event
async def message(sid, data):
    """Handle and store messages"""
    username = connected_users.get(sid, f"User_{sid[:4]}")
    message = data.get('message', '').strip()
    
    if message:
        # Store message in KenobiDB
        message_doc = {
            'type': 'message',
            'username': username,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        db.insert(message_doc)
        
        # Broadcast message to all clients
        await sio.emit('message', {
            'username': username,
            'message': message,
            'timestamp': message_doc['timestamp']
        }, room=None)

async def update_user_list():
    """Broadcast updated user list to all clients"""
    await sio.emit('user_list', list(connected_users.values()), room=None)

# Attach Socket.IO to the ASGI app
asgi_app = MyApp()
app = socketio.ASGIApp(sio, asgi_app)

# Ensure database is closed properly on shutdown
import atexit
atexit.register(db.close)
