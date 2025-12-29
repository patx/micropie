import os
import time
import socketio
from micropie import App
from mongokv import Mkv

# ---------------- Config ----------------
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000", # add your domain here
]

MONGO_URI = "mongodb://localhost:27017"
presence = Mkv(MONGO_URI, db_name="presence", collection_name="presence")

# Presence TTL: streamer is considered offline if no heartbeat within this window
STREAMER_TTL_SECONDS = 45

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS,
    ping_interval=25,
    ping_timeout=60,
)


class MyApp(App):
    async def index(self):
        return "Use /stream/<username> or /watch/<username>"

    async def stream(self, username: str):
        return await self._render_template("stream.html", username=username)

    async def watch(self, username: str):
        return await self._render_template("watch.html", username=username)


# ---------------- Presence helpers (mongoKV) ----------------
def _k_sid(username: str) -> str:
    return f"streamer_sid:{username}"

def _k_seen(username: str) -> str:
    return f"streamer_seen:{username}"

def _k_user_by_sid(sid: str) -> str:
    return f"streamer_user_by_sid:{sid}"

def _k_token(username: str) -> str:
    return f"streamer_token:{username}"


async def _now() -> int:
    return int(time.time())


async def _get_streamer_record(username: str) -> tuple[str | None, int | None]:
    try:
        sid = await presence.get(_k_sid(username))
        seen = await presence.get(_k_seen(username))
        return sid, seen
    except KeyError:
        return None, None


async def get_streamer_sid_if_fresh(username: str) -> str | None:
    sid, seen = await _get_streamer_record(username)
    if not sid or not isinstance(seen, int):
        return None
    if (await _now()) - seen > STREAMER_TTL_SECONDS:
        return None
    return sid


async def clear_streamer(username: str):
    for key in (_k_sid(username), _k_seen(username), _k_token(username)):
        try:
            await presence.delete(key)
        except Exception:
            pass


async def streamer_still_owner(username: str, sid: str) -> bool:
    current = await get_streamer_sid_if_fresh(username)
    return current == sid


async def claim_stream_username(username: str, sid: str, stream_token: str | None) -> tuple[bool, str | None]:
    """
    Returns (ok, reason).
    - If a fresh streamer exists and token doesn't match -> deny "taken"
    - If token matches (same browser rejoin), allow takeover
    - If no fresh streamer exists, claim it
    """
    existing_sid = await get_streamer_sid_if_fresh(username)

    stored_token = None
    try:
        stored_token = await presence.get(_k_token(username))
    except KeyError:
        stored_token = None

    # Someone is live and it's not us: only allow if token matches
    if existing_sid and existing_sid != sid:
        if not stored_token or not stream_token or stored_token != stream_token:
            return False, "taken"

    now = await _now()
    await presence.set(_k_sid(username), sid)
    await presence.set(_k_seen(username), now)
    await presence.set(_k_user_by_sid(sid), username)

    # Bind token on first claim
    if stream_token and (stored_token is None):
        await presence.set(_k_token(username), stream_token)

    return True, None


# ---------------- Socket.IO Events ----------------
@sio.event
async def connect(sid, environ):
    print(f"[connect] {sid}")


@sio.event
async def disconnect(sid):
    print(f"[disconnect] {sid}")
    # cleanup if this sid was a streamer
    try:
        username = await presence.get(_k_user_by_sid(sid))
    except KeyError:
        return

    if await streamer_still_owner(username, sid):
        await clear_streamer(username)

    try:
        await presence.delete(_k_user_by_sid(sid))
    except Exception:
        pass


@sio.on("join_room")
async def join_room(sid, data):
    username = (data or {}).get("username")
    role = (data or {}).get("role")  # "streamer" or "watcher"
    stream_token = (data or {}).get("streamToken")
    if not username:
        return

    await sio.enter_room(sid, username)

    if role == "streamer":
        ok, reason = await claim_stream_username(username, sid, stream_token)
        if not ok:
            await sio.emit("stream_denied", {"username": username, "reason": reason}, to=sid)
            await sio.leave_room(sid, username)
            await sio.disconnect(sid)
            print(f"[join_room] DENIED streamer '{username}' to {sid} reason={reason}")
            return

        await sio.emit("stream_accepted", {"username": username}, to=sid)
        print(f"[join_room] STREAMER {sid} claimed '{username}'")

    else:
        print(f"[join_room] WATCHER {sid} joined '{username}'")


@sio.on("streamer_heartbeat")
async def streamer_heartbeat(sid, data):
    username = (data or {}).get("username")
    if not username:
        return
    if await streamer_still_owner(username, sid):
        await presence.set(_k_seen(username), await _now())


@sio.on("new_watcher")
async def new_watcher(sid, data):
    print(f"[new_watcher] raw sid={sid} data={data}")
    username = (data or {}).get("username")
    if not username:
        return

    streamer_sid = await get_streamer_sid_if_fresh(username)
    print(f"[new_watcher] watcher {sid} wants '{username}', streamer={streamer_sid}")

    if streamer_sid:
        await sio.emit("new_watcher", {"watcherSid": sid}, to=streamer_sid)
    else:
        await sio.emit("stream_offline", {"username": username}, to=sid)


@sio.on("offer")
async def handle_offer(sid, data):
    username = (data or {}).get("username")
    watcher_sid = (data or {}).get("watcherSid")
    offer_sdp = (data or {}).get("offer")
    offer_type = (data or {}).get("offerType", "offer")

    # Only current owner can send offers for this username
    if not username or not await streamer_still_owner(username, sid):
        await sio.emit("stream_denied", {"username": username, "reason": "not_owner"}, to=sid)
        return

    if watcher_sid:
        await sio.emit(
            "offer",
            {"offer": offer_sdp, "offerType": offer_type, "streamerSid": sid},
            to=watcher_sid,
        )


@sio.on("answer")
async def handle_answer(sid, data):
    streamer_sid = (data or {}).get("streamerSid")
    answer_sdp = (data or {}).get("answer")
    answer_type = (data or {}).get("answerType", "answer")

    if streamer_sid:
        await sio.emit(
            "answer",
            {"answer": answer_sdp, "answerType": answer_type, "watcherSid": sid},
            to=streamer_sid,
        )


@sio.on("ice-candidate")
async def handle_ice_candidate(sid, data):
    target_sid = (data or {}).get("targetSid")
    candidate = (data or {}).get("candidate")
    sdp_mid = (data or {}).get("sdpMid")
    sdp_mline_index = (data or {}).get("sdpMLineIndex")

    # Optional hardening: streamer ownership check
    username = (data or {}).get("username")
    role = (data or {}).get("role")
    if role == "streamer" and username:
        if not await streamer_still_owner(username, sid):
            await sio.emit("stream_denied", {"username": username, "reason": "not_owner"}, to=sid)
            return

    if target_sid:
        await sio.emit(
            "ice-candidate",
            {
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index,
                "senderSid": sid,
            },
            to=target_sid,
        )


asgi_app = MyApp()
app = socketio.ASGIApp(sio, other_asgi_app=asgi_app)

