from micropie import App
from mongokv import Mkv


class Root(App):
    def __init__(self):
        super().__init__()
        self.pastes = Mkv("mongodb://localhost:27017")

    async def index(self, paste_content=None):
        if self.request.method == "POST":
            # Auto-generate an _id because key=None
            new_id = await self.pastes.set(None, paste_content)
            return self._redirect(f"/paste/{new_id}")

        return await self._render_template("index.html")

    async def paste(self, paste_id, delete=None):
        if delete == "delete":
            await self.pastes.remove(paste_id)
            return self._redirect("/")

        paste = await self.pastes.get(paste_id)

        return await self._render_template(
            "paste.html",
            paste_id=paste_id,
            paste_content=paste,
        )


app = Root()

