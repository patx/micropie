from html import escape
import os
import uuid
from typing import Optional, Dict, List, Tuple, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature
from MicroPie import App, HttpMiddleware, Request, SESSION_TIMEOUT


class SignedSessionMiddleware(HttpMiddleware):
    """Middleware to sign and verify session cookies using itsdangerous."""
    def __init__(self, app: App, secret_key: str, max_age: int = SESSION_TIMEOUT):
        self.app = app  # Store the App instance
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.max_age = max_age

    async def before_request(self, request: Request) -> Optional[Dict]:
        """Verify the session_id cookie before processing the request."""
        cookies = self.app._parse_cookies(request.headers.get("cookie", ""))
        session_id = cookies.get("session_id", "")
        try:
            verified_id = self.serializer.loads(session_id, max_age=self.max_age)
            request.session = await self.app.session_backend.load(verified_id) or {}
        except BadSignature:
            request.session = {}  # Invalid or expired session_id
        return None

    async def after_request(
        self, request: Request, status_code: int, response_body: Any, extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        """Sign and set the session_id cookie after processing the request."""
        if request.session:
            cookies = self.app._parse_cookies(request.headers.get("cookie", ""))
            session_id = cookies.get("session_id", "") or str(uuid.uuid4())
            try:
                session_id = self.serializer.loads(session_id, max_age=self.max_age)
            except BadSignature:
                session_id = str(uuid.uuid4())
            signed_session_id = self.serializer.dumps(session_id)
            current_session = await self.app.session_backend.load(session_id) or {}
            if current_session != request.session:
                await self.app.session_backend.save(session_id, request.session, SESSION_TIMEOUT)
            if not cookies.get("session_id"):
                extra_headers.append(("Set-Cookie", f"session_id={signed_session_id}; Path=/; SameSite=Lax; HttpOnly; Secure;"))
        return None


class Root(App):

    async def index(self):
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        visits = self.request.session["visits"]
        return f"You have visited {escape(str(visits))} times."


app = Root()
app.middlewares.append(SignedSessionMiddleware(app=app, secret_key="my-secret-key"))
