from micropie import App
from collections import deque
import json
import asyncio

class ChatApp(App):
    def __init__(self):
        super().__init__()
        self.messages = deque(maxlen=100)
        self.clients = set()

    async def index(self):
        # Inline HTML for demo purposes
        html = """
        <!doctype html>
        <title>Micropie Chat SSE</title>
        <h1>Micropie Chat SSE Demo</h1>
        <form id="chat-form">
          Name: <input id="username" value="Anonymous" size="10">
          <input id="message" autocomplete="off" size="40">
          <button>Send</button>
        </form>
        <pre id="log"></pre>
        <script>
        const log = document.getElementById('log');
        const usernameInput = document.getElementById('username');
        const messageInput = document.getElementById('message');
        const form = document.getElementById('chat-form');

        const evtSource = new EventSource('/events');
        evtSource.onmessage = function(event) {
          const data = JSON.parse(event.data);
          log.textContent += data.username + ": " + data.message + "\\n";
        };

        form.onsubmit = async function(e) {
          e.preventDefault();
          await fetch('/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              username: usernameInput.value,
              message: messageInput.value,
            })
          });
          messageInput.value = "";
        };
        </script>
        """
        return 200, html, [('Content-Type', 'text/html')]

    async def send(self):
        data = self.request.get_json
        username = data.get("username", "Anonymous")
        message = data.get("message", "")
        if message.strip():
            msg = {"username": username, "message": message}
            self.messages.append(msg)
            # Broadcast to all connected clients
            for client in self.clients.copy():
                try:
                    await client.put(json.dumps(msg))
                except Exception:
                    self.clients.discard(client)
        return 200, {"status": "success"}

    async def events(self):
        async def stream():
            queue = asyncio.Queue()
            self.clients.add(queue)
            try:
                for msg in self.messages:
                    yield f"data: {json.dumps(msg)}\n\n"
                while True:
                    try:
                        msg = await queue.get()
                        if msg is None:
                            break
                        yield f"data: {msg}\n\n"
                    except asyncio.CancelledError:
                        break
            finally:
                self.clients.discard(queue)
        return 200, stream(), [
            ('Content-Type', 'text/event-stream'),
            ('Cache-Control', 'no-cache'),
            ('Connection', 'keep-alive')
        ]

app = ChatApp()
