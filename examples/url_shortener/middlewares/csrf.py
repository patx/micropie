import asyncio
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from micropie import HttpMiddleware, App, Request


class CSRFMiddleware(HttpMiddleware):
    """
    MicroPie-ready CSRF middleware using itsdangerous + session binding.

    - Verifies on POST/PUT/PATCH/DELETE
    - Accepts token from body (form or JSON) or 'X-CSRF-Token' header
    - For multipart/form-data, strongly prefer header (parser may still be streaming)
    - Token payload includes the session_id (when present) to bind token to that session
    - Emits 'X-CSRF-Token' **only** when we create/rotate one during this request
    - Supports exempt_paths (e.g. webhook endpoints like /sms_order)
    """

    def __init__(
        self,
        app: App,
        secret_key: str,
        *,
        max_age: int = 24 * 3600,  # 24 hours
        trusted_origins: Optional[List[str]] = None,
        body_field: str = "csrf_token",
        header_name: str = "x-csrf-token",
        require_header_for_multipart: bool = True,
        exempt_paths: Optional[List[str]] = None,
    ):
        self.app = app
        self.serializer = URLSafeTimedSerializer(secret_key, salt="csrf-token")
        self.max_age = max_age
        self.trusted = set(trusted_origins or [])
        self.body_field = body_field
        self.header_name = header_name.lower()
        self.require_header_for_multipart = require_header_for_multipart
        self.exempt_paths = set(exempt_paths or [])

    # ---------- helpers ----------

    def _is_mutating(self, method: str) -> bool:
        return method in ("POST", "PUT", "PATCH", "DELETE")

    def _is_multipart(self, ct: str) -> bool:
        return "multipart/form-data" in (ct or "")

    def _origin_ok(self, headers: Dict[str, str]) -> bool:
        if not self.trusted:
            return True
        origin = headers.get("origin")
        referer = headers.get("referer")
        for hdr in (origin, referer):
            if not hdr:
                continue
            try:
                p = urlparse(hdr)
                base = f"{p.scheme}://{p.netloc}"
                if base in self.trusted:
                    return True
            except Exception:
                pass
        return False

    def _get_session_id(self, request: Request) -> Optional[str]:
        cookie = request.headers.get("cookie", "")
        if "session_id=" in cookie:
            return cookie.split("session_id=", 1)[1].split(";", 1)[0].strip() or None
        return None

    def _issue_token(self, session_id: Optional[str]) -> str:
        payload = {"nonce": str(uuid.uuid4())}
        if session_id:
            payload["sid"] = session_id
        return self.serializer.dumps(payload)

    async def _extract_submitted_token(self, request: Request) -> Optional[str]:
        ct = request.headers.get("content-type", "")
        if self._is_multipart(ct) and self.require_header_for_multipart:
            token = request.headers.get(self.header_name)
            if token:
                return token

        lst = request.body_params.get(self.body_field)
        if not lst and self._is_multipart(ct):
            while not request.body_parsed:
                lst = request.body_params.get(self.body_field)
                if lst:
                    break
                await asyncio.sleep(0)

        if lst and isinstance(lst, list) and lst:
            return lst[0]

        j = getattr(request, "get_json", None)
        if isinstance(j, dict):
            tok = j.get(self.body_field)
            if isinstance(tok, str):
                return tok

        return request.headers.get(self.header_name)

    # ---------- middleware hooks ----------

    async def before_request(self, request: Request) -> Optional[Dict]:
        path = request.scope.get("path", "")

        # Exempt specific paths (e.g. /sms_order webhook)
        if path in self.exempt_paths:
            return None

        if "csrf_token" not in request.session:
            sid = self._get_session_id(request)
            request.session["csrf_token"] = self._issue_token(sid)
            setattr(request, "_csrf_emit", request.session["csrf_token"])

        if not self._is_mutating(request.method):
            return None

        if not self._origin_ok(request.headers):
            return {"status_code": 403, "body": "Forbidden: invalid origin/referer"}

        submitted = await self._extract_submitted_token(request)
        if not submitted:
            return {"status_code": 403, "body": "Missing CSRF token"}

        try:
            data = self.serializer.loads(submitted, max_age=self.max_age)
        except SignatureExpired:
            return {"status_code": 403, "body": "<h1>Expired CSRF token, please reload the page and try again.</h1>"}
        except BadSignature:
            return {"status_code": 403, "body": "<h1>Invalid CSRF token signature, please reload the page and try again.</h1>"}

        sid = self._get_session_id(request)
        token_sid = data.get("sid")
        if token_sid is not None and (sid != token_sid):
            return {"status_code": 403, "body": "Invalid CSRF token for this session"}

        sid_now = self._get_session_id(request)
        new_token = self._issue_token(sid_now)
        request.session["csrf_token"] = new_token
        setattr(request, "_csrf_emit", new_token)

        return None

    async def after_request(
        self,
        request: Request,
        status_code: int,
        response_body: Any,
        extra_headers: List[Tuple[str, str]],
    ) -> Optional[Dict]:
        to_emit = getattr(request, "_csrf_emit", None)
        if to_emit:
            extra_headers.append(("X-CSRF-Token", to_emit))
        return None

