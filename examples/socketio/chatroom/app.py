import socketio
from MicroPie import App
from kenobi import KenobiDB
from datetime import datetime
import asyncio
import re
from urllib.parse import unquote

# KenobiDB setup
db = KenobiDB("chat.db")

# Create a Socket.IO server with CORS support
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Store connected users by channel {channel: {sid: username}}
connected_users = {}

# Store channel passwords {channel: password or None}
channel_passwords = {}

# Create the MicroPie server
class MyApp(App):
    async def index(self):
        """Render channel creation page"""
        return await self._render_template("chat.html", is_index=True)

    async def channel(self, channel_name):
        """Render specific channel page"""
        channel_name = unquote(channel_name)
        # Validate channel name
        if not re.match(r'^[a-zA-Z0-9_-]{1,30}$', channel_name):
            return {"error": "Invalid channel name"}, 400
        return await self._render_template("chat.html", channel=channel_name, is_index=False)

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Remove user from all channels
    for channel in connected_users:
        if sid in connected_users[channel]:
            del connected_users[channel][sid]
            await update_user_list(channel)

@sio.event
async def join_channel(sid, data):
    """Handle joining a channel with optional password"""
    channel = data.get('channel', '').strip()
    password = data.get('password', '')
    username = data.get('username', '').strip()

    if not channel or not re.match(r'^[a-zA-Z0-9_-]{1,30}$', channel):
        await sio.emit('error', {'message': 'Invalid channel name'}, room=sid)
        return

    if not username or len(username) > 20:
        await sio.emit('error', {'message': 'Invalid username'}, room=sid)
        return

    # Initialize channel if it doesn't exist
    if channel not in connected_users:
        connected_users[channel] = {}

    # Check password if required
    if channel in channel_passwords and channel_passwords[channel] and password != channel_passwords[channel]:
        await sio.emit('error', {'message': 'Incorrect password'}, room=sid)
        return

    # Check if username is taken in this channel
    if username in connected_users[channel].values():
        await sio.emit('error', {'message': 'Username already taken'}, room=sid)
        return

    # Join the socket.io room for this channel
    await sio.enter_room(sid, channel)
    
    # Add user to channel
    connected_users[channel][sid] = username
    print(f"User {sid} joined channel {channel} as {username}")

    # Send recent messages for this channel
    try:
        # Get all messages with type="message"
        all_messages = db.search("type", "message", limit=1000)  # Use a high limit to ensure we get all messages
        # Filter messages for the specific channel
        recent_messages = [msg for msg in all_messages if msg.get('channel') == channel][:50]  # Limit to 50
        print(f"Retrieved {len(recent_messages)} recent messages for channel {channel}")
        for msg in recent_messages:
            await sio.emit('message', {
                'username': msg['username'],
                'message': msg['message'],
                'timestamp': msg['timestamp']
            }, room=sid)
    except Exception as e:
        print(f"Error retrieving messages for channel {channel}: {str(e)}")
        await sio.emit('error', {'message': 'Failed to load recent messages'}, room=sid)

    # Update user list for this channel
    await update_user_list(channel)

    # Confirm successful join to the client
    await sio.emit('join_success', room=sid)

@sio.event
async def create_channel(sid, data):
    """Handle channel creation"""
    channel = data.get('channel', '').strip()
    password = data.get('password', '').strip() or None

    if not channel or not re.match(r'^[a-zA-Z0-9_-]{1,30}$', channel):
        await sio.emit('error', {'message': 'Invalid channel name'}, room=sid)
        return

    if channel in connected_users:
        await sio.emit('error', {'message': 'Channel already exists'}, room=sid)
        return

    # Create new channel
    connected_users[channel] = {}
    channel_passwords[channel] = password
    await sio.emit('channel_created', {'channel': channel}, room=sid)

@sio.event
async def message(sid, data):
    """Handle and store messages"""
    channel = data.get('channel', '').strip()
    message = data.get('message', '').strip()
    
    if not channel or not message:
        return

    username = None
    for chan, users in connected_users.items():
        if sid in users:
            username = users[sid]
            break

    if not username:
        return

    # Store message in KenobiDB
    message_doc = {
        'type': 'message',
        'channel': channel,
        'username': username,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    db.insert(message_doc)
    
    # Broadcast message to channel
    await sio.emit('message', {
        'username': username,
        'message': message,
        'timestamp': message_doc['timestamp']
    }, room=channel)

async def update_user_list(channel):
    """Broadcast updated user list to channel"""
    if channel in connected_users:
        print(f"Broadcasting user list for channel {channel}: {list(connected_users[channel].values())}")
        await sio.emit('user_list', list(connected_users[channel].values()), room=channel)

# Attach Socket.IO to the ASGI app
asgi_app = MyApp()
app = socketio.ASGIApp(sio, asgi_app)

# Ensure database is closed properly on shutdown
import atexit
atexit.register(db.close)
