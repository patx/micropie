"""Use MicroPie's session-ID policy hooks for signed cookie identifiers."""

from html import escape
import uuid

from itsdangerous import BadSignature, URLSafeTimedSerializer

from micropie import App


serializer = URLSafeTimedSerializer("my-secret-key", salt="session-id")


def create_signed_session_id() -> str:
    return serializer.dumps(str(uuid.uuid4()))


def validate_signed_session_id(value: str):
    try:
        serializer.loads(value)
    except BadSignature:
        return None
    return value


class Root(App):
    async def index(self):
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        visits = self.request.session["visits"]
        return f"You have visited {escape(str(visits))} times."


app = Root(
    session_id_factory=create_signed_session_id,
    session_id_validator=validate_signed_session_id,
)
