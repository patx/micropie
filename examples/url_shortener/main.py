from string import ascii_letters, digits
from secrets import choice

from micropie import App
from mongokv import Mkv

# Import middlewares and session backends
from middlewares.rate_limit import MongoRateLimitMiddleware
from middlewares.csrf import CSRFMiddleware
from sessions.mongo_session import MkvSessionBackend


# EXAMPLE KEYS/URI, in production use/generate your own and save it as an 
# environment variables, do not hard code them like these demos HINT: You 
# can use `secrets.token_urlsafe(64)` to generate your CSRF secret key
URL_ROOT = "http://localhost:8000/"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "shorty"
CSRF_KEY = "wzWf0CsZr3LfrgPVc9RqHFVUmyXsYT-k8hnGt41bMGU"

# Create an mongoKV instance using our URI
db = Mkv(MONGO_URI, db_name=DB_NAME, collection_name="urls")


# Our main app class
class Shorty(App):

    def _generate_id(self, length: int = 8) -> str:
        return "".join(choice(ascii_letters + digits) for _ in range(length))

    async def index(self, url_str: str | None = None):
        if url_str:
            if self.request.method == "POST":
                while True:
                    short_id = self._generate_id()
                    try:
                        await db.get(short_id)
                    except KeyError:
                        break

                await db.set(short_id, url_str)
                return await self._render_template(
                    "success.html",
                    url_id=url_str,
                    short_id=short_id,
                    url_root=URL_ROOT,
                )

            real_url = await db.get(url_str, "/")
            if not isinstance(real_url, str) or not real_url.startswith(("http://", "https://")):
                return self._redirect("/")
            return self._redirect(real_url)

        return await self._render_template("index.html", request=self.request)


app = Shorty(session_backend=MkvSessionBackend(
    mongo_uri=MONGO_URI, 
    db_name=DB_NAME
    )
)
app.middlewares.append(
    MongoRateLimitMiddleware(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        allowed_hosts=None,          # don't enforce host allowlist, change in prod
        trust_proxy_headers=False,   # change in prod
        require_cf_ray=False,
    )
)
app.middlewares.append(
    CSRFMiddleware(
        app=app,
        secret_key=CSRF_KEY
    )
)

