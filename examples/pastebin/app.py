from micropie import App
from mongokv import Mkv


pastes = Mkv("mongodb://localhost:27017")


class Root(App):

    async def index(self, paste_content=None):
        if self.request.method == "POST":
            new_id = await pastes.set(None, paste_content)
            return self._redirect(f"/paste/{new_id}")

        return await self._render_template("index.html")

    async def paste(self, paste_id):
        paste = await pastes.get(paste_id, "404: Paste Not Found")
        return await self._render_template("paste.html",
            paste_id=paste_id,
            paste_content=paste,
        )


app = Root()

