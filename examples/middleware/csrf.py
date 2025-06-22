from typing import Optional, Dict, List, Tuple, Any
from html import escape
import uuid
from itsdangerous import URLSafeTimedSerializer, BadSignature
from MicroPie import App, HttpMiddleware, Request


class CSRFMiddleware(HttpMiddleware):
    """Middleware for CSRF protection using itsdangerous-signed tokens."""
    def __init__(self, app: App, secret_key: str, max_age: int = 8 * 3600):
        self.app = app  # Store the App instance
        self.serializer = URLSafeTimedSerializer(secret_key, salt="csrf-token")
        self.max_age = max_age

    async def before_request(self, request: Request) -> Optional[Dict]:
        """Verify CSRF token for POST/PUT/PATCH requests and generate a new token if needed."""
        # Extract session ID from cookies or generate a new one
        session_id = request.headers.get("cookie", "").split("session_id=")[-1].split(";")[0] if "session_id=" in request.headers.get("cookie", "") else str(uuid.uuid4())

        if request.method in ("POST", "PUT", "PATCH"):
            print(f"Request body_params: {request.body_params}")  # Debugging
            submitted_token = request.body_params.get("csrf_token", [""])[0]
            print(f"Submitted CSRF token: {submitted_token}")  # Debugging
            if not submitted_token:
                return {"status_code": 403, "body": "Missing CSRF token"}
            try:
                # Verify the submitted token's signature
                self.serializer.loads(submitted_token, max_age=self.max_age)
            except BadSignature:
                return {"status_code": 403, "body": "Invalid or expired CSRF token"}

        # Generate a new CSRF token if one doesn't exist in the session
        if "csrf_token" not in request.session:
            csrf_token = str(uuid.uuid4())
            signed_token = self.serializer.dumps(csrf_token)
            request.session["csrf_token"] = signed_token
            # Save the session
            print(f"Saving session with CSRF token: {signed_token}")  # Debugging
            await self.app.session_backend.save(session_id, request.session, self.max_age)

        return None

    async def after_request(
        self, request: Request, status_code: int, response_body: Any, extra_headers: List[Tuple[str, str]]
    ) -> Optional[Dict]:
        """Include CSRF token in response headers for client-side use."""
        if request.session.get("csrf_token"):
            extra_headers.append(("X-CSRF-Token", request.session["csrf_token"]))
        return None


class Root(App):

    async def index(self):
        csrf_token = self.request.session.get("csrf_token", "")
        print(f"Rendering form with CSRF token: {csrf_token}")
        return f"""<form method="POST" action="/submit">
            <input type="hidden" name="csrf_token" value="{escape(csrf_token)}">
            <input type="text" name="name">
            <button type="submit">Submit</button>
            </form>"""

    async def submit(self):
        if self.request.method == "POST":
            name = self.request.body_params.get("name", ["World"])[0]
            return f"Hello {name}"


app = Root()
app.middlewares.append(CSRFMiddleware(app=app, secret_key="my-secret-key"))
