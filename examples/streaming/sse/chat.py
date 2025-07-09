"""
Example chat application using server sent events.
This works with `uvicorn` but works better with `daphne`.
This kind of application is better suited for websockets, 
but is a good example nonetheless.
"""

from micropie import App
from collections import deque
import json
import asyncio

class ChatApp(App):
    def __init__(self):
        super().__init__()
        # Store messages in a deque with a max length
        self.messages = deque(maxlen=100)
        # Store connected clients
        self.clients = set()

    async def index(self):
        """Serve the chat interface."""
        return await self._render_template('chat.html')

    async def send(self):
        data = self.request.get_json
        username = data.get('username', 'Anonymous')
        message = data.get('message', '')
        
        if message.strip():
            msg = {'username': username, 'message': message}
            self.messages.append(msg)
            
            # Broadcast to all connected clients
            for client in self.clients.copy():
                try:
                    await client.put(json.dumps(msg))
                except Exception:
                    self.clients.discard(client)
                    
        return 200, {'status': 'success'}

    async def events(self):
        """Stream chat messages via server-sent events."""
        async def stream():
            client_queue = asyncio.Queue()
            self.clients.add(client_queue)
            
            try:
                # Send existing messages first
                for msg in self.messages:
                    yield f"data: {json.dumps(msg)}\n\n"
                
                # Keep connection open and send new messages
                while True:
                    msg = await client_queue.get()
                    yield f"data: {msg}\n\n"
                    
            except asyncio.CancelledError:
                pass
                
            finally:
                self.clients.discard(client_queue)

        return 200, stream(), [
            ('Content-Type', 'text/event-stream'),
            ('Cache-Control', 'no-cache'),
            ('Connection', 'keep-alive')
        ]

app = ChatApp()
