"""
URL Shortener using MicroPie and PyMongo. Live at https://erd.sh/


Copyright 2025 Harrison Erd

Redistribution and use in source and binary forms, with or without 
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, 
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, 
this list of conditions and the following disclaimer in the documentation 
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its 
contributors may be used to endorse or promote products derived from this 
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS 
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from string import ascii_letters, digits
from secrets import choice
from datetime import datetime, timedelta

from micropie import App
from pymongo import AsyncMongoClient, ReturnDocument

from middlewares.rate_limit import MongoRateLimitMiddleware
from middlewares.csrf import CSRFMiddleware
from middlewares.sub_app import SubAppMiddleware
from sessions.mongo_session import MkvSessionBackend


URL_ROOT = "https://localhost:8000/"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "shorty"
COLLECTION = "urls"
CSRF_KEY = "wzDf0CcZr3LgrgPVc2RqHFVUmyXsYT-k8kjGt41bMGU"

mongo = AsyncMongoClient(MONGO_URI)
urls = mongo[DB_NAME][COLLECTION]


def _generate_id(length: int = 6) -> str:
    return "".join(choice(ascii_letters + digits) for _ in range(length))


def _parse_expires_in(value) -> int | None:
    """
    API-only: expires_in seconds.
    Returns None if missing/invalid. Clamps to a sane max (30 days).
    """
    if value is None:
        return None
    try:
        n = int(value)
    except Exception:
        return None
    if n <= 0:
        return None
    MAX_EXPIRES_IN = 60 * 60 * 24 * 30  # 30 days
    return min(n, MAX_EXPIRES_IN)


def _parse_max_clicks(value) -> int | None:
    """
    API-only: max_clicks.
    Returns None if missing/invalid. Clamps to a sane max.
    """
    if value is None:
        return None
    try:
        n = int(value)
    except Exception:
        return None
    if n <= 0:
        return None
    MAX_MAX_CLICKS = 1_000_000  # safety cap
    return min(n, MAX_MAX_CLICKS)


def _parse_hide_stats_on_expire(value) -> bool | None:
    """
    API-only: hide_stats_on_expire.
    Returns True/False if provided, else None (unset).
    Accepts: true/false, 1/0, "true"/"false", "yes"/"no", "on"/"off".
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y", "on"}:
            return True
        if v in {"false", "0", "no", "n", "off"}:
            return False
    return None


class Shorty(App):

    async def index(self, url_str: str | None = None):
        if url_str:
            if self.request.method == "POST":
                return await self._create_short_link(url_str)

            if url_str.endswith("+"):
                return await self._stats_page(url_str)

            return await self._redirect_link(url_str)

        return await self._render_template("index.html", request=self.request)

    async def _create_short_link(self, url_str: str):
        if not isinstance(url_str, str) or not url_str.startswith(("https://")):
            return 400, await self._render_template("400.html")

        while True:
            short_id = _generate_id()
            exists = await urls.find_one({"_id": short_id})
            if not exists:
                break

        await urls.insert_one({
            "_id": short_id,
            "url": url_str,
            "clicks": 0,
            "created_at": datetime.utcnow(),
            "last_clicked_at": None,
        })

        return await self._render_template(
            "success.html",
            url_id=url_str,
            short_id=short_id,
            url_root=URL_ROOT,
        )

    async def _redirect_link(self, url_str: str):
        """
        Enforces API-only constraints if present:
        - expires_at (datetime): link is invalid once now >= expires_at
        - max_clicks (int): link is invalid once clicks >= max_clicks

        We enforce atomically by filtering the update so the increment only happens
        when the link is still valid.
        """
        now = datetime.utcnow()
        query = {
            "_id": url_str,
            "$and": [
                {
                    "$or": [
                        {"expires_at": {"$exists": False}},
                        {"expires_at": None},
                        {"expires_at": {"$gt": now}},
                    ]
                },
                {
                    "$or": [
                        {"max_clicks": {"$exists": False}},
                        {"max_clicks": None},
                        {"$expr": {"$lt": ["$clicks", "$max_clicks"]}},
                    ]
                },
            ],
        }

        doc = await urls.find_one_and_update(
            query,
            {
                "$inc": {"clicks": 1},
                "$set": {"last_clicked_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )

        if not doc:
            return 404, await self._render_template("404.html")

        return self._redirect(doc["url"])

    async def _stats_page(self, url_str: str):
        short_code = url_str[:-1]
        doc = await urls.find_one({"_id": short_code})

        if not doc:
            return 404, await self._render_template("404.html")

        # If configured, hide stats once the link is invalid (expired or maxed).
        if doc.get("hide_stats_on_expire") is True:
            now = datetime.utcnow()
            expires_at = doc.get("expires_at")
            max_clicks = doc.get("max_clicks")
            clicks = int(doc.get("clicks", 0))

            expired = isinstance(expires_at, datetime) and now >= expires_at
            maxed = isinstance(max_clicks, int) and clicks >= max_clicks

            if expired or maxed:
                return 410, await self._render_template("410.html")

        return await self._render_template(
            "stats.html",
            short_code=short_code,
            url=doc.get("url"),
            clicks=int(doc.get("clicks", 0)),
            url_root=URL_ROOT,
        )


class ApiApp(App):

    async def index(self):
        return await self._render_template("api.html")

    async def shorten(self):
        if self.request.method != "POST":
            return 405, {"error": "Method Not Allowed"}

        data = self.request.get_json
        url_str = data.get("url")

        if not isinstance(url_str, str):
            return 400, {"error": "Invalid JSON or missing 'url' key"}

        if not url_str.startswith(("https://")):
            return 400, {"error": "Invalid URL"}

        expires_in = _parse_expires_in(data.get("expires_in"))
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)) if expires_in else None

        max_clicks = _parse_max_clicks(data.get("max_clicks"))

        hide_stats_on_expire = _parse_hide_stats_on_expire(data.get("hide_stats_on_expire"))

        while True:
            short_id = _generate_id()
            exists = await urls.find_one({"_id": short_id})
            if not exists:
                break

        await urls.insert_one({
            "_id": short_id,
            "url": url_str,
            "clicks": 0,
            "created_at": datetime.utcnow(),
            "last_clicked_at": None,
            # API-only controls:
            **({"expires_at": expires_at} if expires_at else {}),
            **({"max_clicks": max_clicks} if max_clicks else {}),
            **({"hide_stats_on_expire": hide_stats_on_expire} if hide_stats_on_expire is not None else {}),
        })

        return {
            "status": "success",
            "long_url": url_str,
            "short_id": short_id,
            "short_url": f"{URL_ROOT}{short_id}",
            "expires_at": expires_at.isoformat() + "Z" if expires_at else None,
            "max_clicks": max_clicks,
            "hide_stats_on_expire": hide_stats_on_expire,
        }

    async def stats(self, short_id: str):
        if self.request.method != "GET":
            return 405, {"error": "Method Not Allowed"}

        if not isinstance(short_id, str) or not short_id:
            return 400, {"error": "Missing short_id"}

        doc = await urls.find_one({"_id": short_id})
        if not doc:
            return 404, {"error": "Not Found"}

        # If configured, hide stats once the link is invalid (expired or maxed).
        if doc.get("hide_stats_on_expire") is True:
            now = datetime.utcnow()
            expires_at = doc.get("expires_at")
            max_clicks = doc.get("max_clicks")
            clicks = int(doc.get("clicks", 0))

            if isinstance(expires_at, datetime) and now >= expires_at:
                return 410, {"error": "Gone"}

            if isinstance(max_clicks, int) and clicks >= max_clicks:
                return 410, {"error": "Gone"}

        created_at = doc.get("created_at")
        last_clicked_at = doc.get("last_clicked_at")
        expires_at = doc.get("expires_at")
        max_clicks = doc.get("max_clicks")
        hide_stats_on_expire = doc.get("hide_stats_on_expire")

        return {
            "status": "success",
            "short_id": short_id,
            "short_url": f"{URL_ROOT}{short_id}",
            "long_url": doc.get("url"),
            "clicks": int(doc.get("clicks", 0)),
            "created_at": created_at.isoformat() + "Z" if created_at else None,
            "last_clicked_at": last_clicked_at.isoformat() + "Z" if last_clicked_at else None,
            "expires_at": expires_at.isoformat() + "Z" if isinstance(expires_at, datetime) else None,
            "max_clicks": int(max_clicks) if isinstance(max_clicks, int) else None,
            "hide_stats_on_expire": hide_stats_on_expire if isinstance(hide_stats_on_expire, bool) else None,
        }


app = Shorty(
    session_backend=MkvSessionBackend(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
    )
)

app.middlewares.append(
    MongoRateLimitMiddleware(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        allowed_hosts=None,
        trust_proxy_headers=False,
        require_cf_ray=False,
        limit_methods={"GET", "POST"},
    )
)

app.middlewares.append(
    CSRFMiddleware(
        app=app,
        secret_key=CSRF_KEY,
        exempt_paths=[
            "/api/v1/shorten",
            "/api/v1/stats",
        ],
    )
)

app.middlewares.append(
    SubAppMiddleware(
        mount_path="/api/v1",
        subapp=ApiApp(),
    )
)

