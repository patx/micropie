from string import ascii_letters
from secrets import choice

from micropie import App
from mongokv import Mkv

URLROOT = "http://localhost:8000/"
db = Mkv("mongodb://localhost:27017")


class Shorty(App):

    async def index(self, url_str: str | None = None):
        if url_str:

            if self.request.method == "POST":
                short_id = "".join(choice(ascii_letters) for _ in range(6))
                await db.set(short_id, url_str)
                return await self._render_template("success.html", 
                    url_id=url_str, short_id=short_id, url_root=URLROOT)
            
            real_url = await db.get(url_str, "/")
            return self._redirect(real_url)
    
        return await self._render_template("index.html")


app = Shorty()
