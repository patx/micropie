import socketio
from MicroPie import App

# 1) Create the Async Socket.IO server and wrap with an ASGI app.
sio = socketio.AsyncServer(async_mode="asgi")

# Keep track of "active" usernames for demonstration
active_users = set()

# 2) Create a MicroPie server class with routes
class MyApp(App):
    async def index(self):
        # A simple response for the root path
        return 'Use /stream/*username* or /watch/*username*'

    async def stream(self, username: str):
        # Mark the username active, render the streamer template
        active_users.add(username)
        return await self._render_template("stream.html", username=username)

    async def watch(self, username: str):
        # Mark the username active, render the watcher template
        return await self._render_template("watch.html", username=username)

#
# ------------------- Socket.IO Events for Signaling --------------------
#

@sio.event
async def connect(sid, environ):
    print(f"[connect] Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[disconnect] Client disconnected: {sid}")

@sio.on("join_room")
async def join_room(sid, data):
    """Each client (streamer or watcher) joins a room named after <username>."""
    username = data.get("username")
    if username:
        active_users.add(username)
        await sio.enter_room(sid, username)
        print(f"[join_room] {sid} joined room '{username}'")

@sio.on("new_watcher")
async def new_watcher(sid, data):
    """
    A watcher informs the server it wants to watch <username>.
    We broadcast 'new_watcher' to the entire room except the watcher,
    so the streamer sees there's a new viewer to create an offer for.
    """
    username = data.get("username")
    watcher_sid = data.get("watcherSid")
    print(f"[new_watcher] {watcher_sid} => watch {username}")
    if username in active_users:
        # Notify others in the room (specifically the streamer)
        await sio.emit("new_watcher",
                       {"watcherSid": watcher_sid},
                       room=username,
                       skip_sid=watcher_sid)

@sio.on("offer")
async def handle_offer(sid, data):
    """
    The streamer sends an offer for a specific watcherSid.
    We forward it directly to that watcherSid.
    """
    username = data.get("username")
    watcher_sid = data.get("watcherSid")
    offer_sdp = data.get("offer")
    offer_type = data.get("offerType")

    print(f"[offer] From streamer {sid} to watcher {watcher_sid}, room={username}")

    # Send the offer ONLY to watcherSid (not the whole room)
    await sio.emit("offer",
                   {
                       "offer": offer_sdp,
                       "offerType": offer_type,
                       "streamerSid": sid
                   },
                   to=watcher_sid)

@sio.on("answer")
async def handle_answer(sid, data):
    """
    The watcher sends back an answer to the streamerSid.
    Forward that to the streamer.
    """
    streamer_sid = data.get("streamerSid")
    answer_sdp = data.get("answer")
    answer_type = data.get("answerType")

    print(f"[answer] From watcher {sid} to streamer {streamer_sid}")

    await sio.emit("answer",
                   {
                       "answer": answer_sdp,
                       "answerType": answer_type,
                       "watcherSid": sid
                   },
                   to=streamer_sid)

@sio.on("ice-candidate")
async def handle_ice_candidate(sid, data):
    """
    Either streamer or watcher can send ICE candidates. We relay them
    to 'targetSid' so the two peers can complete their direct connection.
    """
    target_sid = data.get("targetSid")
    candidate = data.get("candidate")
    sdp_mid = data.get("sdpMid")
    sdp_mline_index = data.get("sdpMLineIndex")

    print(f"[ice-candidate] {sid} => {target_sid}")

    if target_sid:
        await sio.emit("ice-candidate",
                       {
                           "candidate": candidate,
                           "sdpMid": sdp_mid,
                           "sdpMLineIndex": sdp_mline_index,
                           "senderSid": sid
                       },
                       to=target_sid)


asgi_app = MyApp()
app = socketio.ASGIApp(sio, asgi_app)

