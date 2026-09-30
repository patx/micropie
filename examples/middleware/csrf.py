"""Synchronizer-token CSRF protection for a MicroPie application.

Run this example from its directory with::

    pip install "micropie[all]"
    uvicorn app:app --reload

Then open http://127.0.0.1:8000. The built-in in-memory session backend is
convenient for this single-process demo. A real deployment should use a
shared, persistent ``SessionBackend`` when running more than one process.
"""

from __future__ import annotations

import html
import re
import secrets
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

from micropie import App, HttpMiddleware, Request


class CSRFMiddleware(HttpMiddleware):
    """Protect unsafe HTTP methods with a session-bound CSRF token.

    A token is created during the first safe request and stored in the
    server-side session. Clients must echo it in ``X-CSRF-Token`` or in a
    ``csrf_token`` form/JSON field on every unsafe request.

    Multipart requests must use the header because MicroPie streams their
    fields while ``before_request`` is running. Only exempt an endpoint when
    it has separate protection, such as signature verification for a webhook.
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
    TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")

    def __init__(
        self,
        *,
        trusted_origins: Iterable[str] | None = None,
        body_field: str = "csrf_token",
        header_name: str = "x-csrf-token",
        exempt_paths: Iterable[str] = (),
    ) -> None:
        self.body_field = body_field
        self.header_name = header_name.lower()
        self.exempt_paths = frozenset(exempt_paths)
        self.trusted_origins = self._normalize_trusted_origins(trusted_origins)

    @classmethod
    def _normalize_trusted_origins(
        cls, values: Iterable[str] | None
    ) -> frozenset[str]:
        if values is None:
            return frozenset()

        origins = set()
        for value in values:
            origin = cls._origin(value)
            if origin is None:
                raise ValueError(f"Invalid trusted origin: {value!r}")
            origins.add(origin)
        return frozenset(origins)

    @staticmethod
    def _origin(value: str | None) -> str | None:
        """Return a normalized HTTP origin from an Origin or Referer value."""
        if not value:
            return None

        try:
            parsed = urlsplit(value)
            scheme = parsed.scheme.lower()
            hostname = parsed.hostname
            port = parsed.port
        except (TypeError, ValueError):
            return None

        if (
            scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None

        host = hostname.lower()
        if ":" in host:  # Preserve brackets around IPv6 hosts.
            host = f"[{host}]"

        default_port = 80 if scheme == "http" else 443
        authority = host if port in (None, default_port) else f"{host}:{port}"
        return f"{scheme}://{authority}"

    def _origin_is_trusted(self, request: Request) -> bool:
        if not self.trusted_origins:
            return True

        # Prefer Origin. Only use Referer when Origin is absent; an invalid
        # Origin must not be rescued by a valid-looking Referer.
        origin = request.headers.get("origin")
        if origin is not None:
            return self._origin(origin) in self.trusted_origins

        referer = request.headers.get("referer")
        return self._origin(referer) in self.trusted_origins

    def _submitted_token(self, request: Request) -> str | None:
        header_token = request.headers.get(self.header_name)
        if header_token:
            return header_token

        content_type = request.headers.get("content-type", "").lower()
        if "multipart/form-data" in content_type:
            # Multipart parsing is concurrent in MicroPie. Requiring the
            # header avoids waiting for a field that may never arrive.
            return None

        form_token = request.form(self.body_field)
        if form_token:
            return form_token

        json_token = request.json(self.body_field)
        return json_token if isinstance(json_token, str) else None

    @classmethod
    def _valid_session_token(cls, token: Any) -> bool:
        return (
            isinstance(token, str)
            and cls.TOKEN_PATTERN.fullmatch(token) is not None
        )

    async def before_request(self, request: Request) -> dict[str, Any] | None:
        if request.scope.get("path", "") in self.exempt_paths:
            return None

        method = (request.method or "").upper()
        session_token = request.session.get("csrf_token")

        if method in self.SAFE_METHODS:
            if not self._valid_session_token(session_token):
                session_token = secrets.token_urlsafe(32)
                request.session["csrf_token"] = session_token
                request._csrf_token_was_created = session_token
            return None

        if not self._origin_is_trusted(request):
            return {
                "status_code": 403,
                "body": "403 Forbidden: untrusted Origin or Referer",
            }

        submitted_token = self._submitted_token(request)
        if not submitted_token:
            return {
                "status_code": 403,
                "body": "403 Forbidden: missing CSRF token",
            }

        if (
            not self._valid_session_token(session_token)
            or not self._valid_session_token(submitted_token)
            or not secrets.compare_digest(submitted_token, session_token)
        ):
            return {
                "status_code": 403,
                "body": "403 Forbidden: invalid CSRF token",
            }

        return None

    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: list[tuple[str, str]],
    ) -> dict[str, Any] | None:
        # This is useful to clients that first obtain a token with a safe
        # request. HTML templates can instead read request.session directly.
        token = getattr(request, "_csrf_token_was_created", None)
        if token:
            extra_headers.append(("X-CSRF-Token", token))
        return None


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MicroPie CSRF example</title>
  <style>
    body { font: 16px/1.5 system-ui, sans-serif; max-width: 48rem; margin: 3rem auto; padding: 0 1rem; }
    section { border: 1px solid #ccc; border-radius: .5rem; margin: 1rem 0; padding: 1rem; }
    input, button { font: inherit; padding: .45rem .65rem; }
    code, pre { background: #f4f4f4; border-radius: .25rem; padding: .15rem .3rem; }
    pre { min-height: 1.5rem; overflow-wrap: anywhere; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>MicroPie CSRF protection</h1>
  <p>
    This page receives a random token that is stable for the session and never
    used as the session cookie itself. Unsafe requests must echo it back.
  </p>

  <section>
    <h2>HTML form</h2>
    <p>The synchronizer token travels in a hidden form field.</p>
    <form action="/submit_form" method="post">
      <input type="hidden" name="csrf_token" value="__CSRF_TOKEN__">
      <label>Message <input name="message" value="Sent by a protected form"></label>
      <button type="submit">Submit form</button>
    </form>
  </section>

  <section>
    <h2>JSON request</h2>
    <p>JavaScript sends the same token in the <code>X-CSRF-Token</code> header.</p>
    <button id="protected-request">Send protected request</button>
    <button id="unprotected-request">Try without a token</button>
    <pre id="result" aria-live="polite"></pre>
  </section>

  <script>
    const csrfToken = "__CSRF_TOKEN__";
    const result = document.querySelector("#result");

    async function send(includeToken) {
      const headers = {"Content-Type": "application/json"};
      if (includeToken) headers["X-CSRF-Token"] = csrfToken;

      const response = await fetch("/submit_json", {
        method: "POST",
        headers,
        body: JSON.stringify({message: "Sent by a protected JSON request"})
      });
      result.textContent = `${response.status} ${await response.text()}`;
    }

    document.querySelector("#protected-request").onclick = () => send(true);
    document.querySelector("#unprotected-request").onclick = () => send(false);
  </script>
</body>
</html>
"""


class CSRFExample(App):
    async def index(self):
        if self.request.method not in {"GET", "HEAD"}:
            return 405, "405 Method Not Allowed"

        token = html.escape(self.request.session["csrf_token"], quote=True)
        return (
            200,
            PAGE.replace("__CSRF_TOKEN__", token),
            [("Cache-Control", "no-store")],
        )

    async def submit_form(self):
        if self.request.method != "POST":
            return 405, {"error": "Method Not Allowed"}

        return {
            "ok": True,
            "message": self.request.form("message", ""),
            "token_source": "form field",
        }

    async def submit_json(self):
        if self.request.method != "POST":
            return 405, {"error": "Method Not Allowed"}

        token_source = (
            "X-CSRF-Token header"
            if self.request.headers.get("x-csrf-token")
            else "JSON field"
        )
        return {
            "ok": True,
            "message": self.request.json("message", ""),
            "token_source": token_source,
        }


# Local HTTP needs Secure=False so the browser will return the session cookie.
# Keep MicroPie's default Secure=True when deploying this application over HTTPS.
app = CSRFExample(session_cookie_secure=False)
app.middlewares.append(
    CSRFMiddleware(
        trusted_origins={
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        }
    )
)
