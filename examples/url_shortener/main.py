from string import ascii_letters, digits
from secrets import choice

from micropie import App
from mongokv import Mkv

from middlewares.rate_limit import MongoRateLimitMiddleware
from middlewares.csrf import CSRFMiddleware


URL_ROOT = "http://localhost:8000/"
MONGO_URI = "mongodb://localhost:27017"
CSRF_KEY = "wzWf0CsZr3LfrgPVc9RqHFVUmyXsYT-k8hnGt41bMGU"

db = Mkv(MONGO_URI)


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


app = Shorty()
app.middlewares.append(MongoRateLimitMiddleware(mongo_uri=MONGO_URI))
app.middlewares.append(CSRFMiddleware(app=app, secret_key=CSRF_KEY))

