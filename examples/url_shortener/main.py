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
from datetime import datetime

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
        if not isinstance(url_str, str) or not url_str.startswith(("http://", "https://")):
            return self._redirect("/")

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
        doc = await urls.find_one_and_update(
            {"_id": url_str},
            {
                "$inc": {"clicks": 1},
                "$set": {"last_clicked_at": datetime.utcnow()},
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return self._redirect("/")
        return self._redirect(doc["url"])
    

    async def _stats_page(self, url_str: str):
        short_code = url_str[:-1]
        doc = await urls.find_one({"_id": short_code})
        
        if not doc:
            return self._redirect("/")
            
        return await self._render_template(
            "stats.html",
            short_code=short_code,
            url=doc.get("url"),
            clicks=int(doc.get("clicks", 0)),
            created_at=doc.get("created_at"),
            last_clicked_at=doc.get("last_clicked_at"),
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

        if not url_str.startswith(("http://", "https://")):
            return 400, {"error": "Invalid URL"}

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

        return {
            "status": "success",
            "long_url": url_str,
            "short_id": short_id,
            "short_url": f"{URL_ROOT}{short_id}",
        }

    async def stats(self, short_id: str):
        if self.request.method != "GET":
            return 405, {"error": "Method Not Allowed"}

        if not isinstance(short_id, str) or not short_id:
            return 400, {"error": "Missing short_id"}

        doc = await urls.find_one({"_id": short_id})
        if not doc:
            return 404, {"error": "Not Found"}

        created_at = doc.get("created_at")
        last_clicked_at = doc.get("last_clicked_at")

        return {
            "status": "success",
            "short_id": short_id,
            "short_url": f"{URL_ROOT}{short_id}",
            "long_url": doc.get("url"),
            "clicks": int(doc.get("clicks", 0)),
            "created_at": created_at.isoformat() + "Z" if created_at else None,
            "last_clicked_at": last_clicked_at.isoformat() + "Z" if last_clicked_at else None,
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
