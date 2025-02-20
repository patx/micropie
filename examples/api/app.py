from MicroPie import App
from pickledb import AsyncPickleDB
import orjson
from uuid import uuid4

db = AsyncPickleDB('pastes.db')


class PasteApp(App):

    async def paste(self, pid: str = None):
        if self.request.method == "POST":
            # Get content from JSON or form, depending on the Content-Type
            content = self.request.body_params.get('content')[0]
            pid = str(uuid4())
            await db.aset(pid, content)
            return orjson.dumps({
                "status": "success",
                "action": "post",
                "paste_id": pid,
                "content": content
            })

        elif self.request.method == "DELETE":
            await db.aremove(pid)
            return orjson.dumps({
                "status": "success",
                "action": "delete",
                "paste_id": pid
            })

        elif self.request.method == "GET":
            if pid:
                paste = await db.aget(pid)
                if paste is None:
                    return 404, orjson.dumps({
                        "status": "fail",
                        "error": "Paste not found"
                    })
                return orjson.dumps({
                    "status": "success",
                    "action": "get",
                    "paste_id": pid,
                    "content": paste
                })

            all_keys = await db.aall()
            all_pastes = [{
                "paste_id": key,
                "content": await db.aget(key)
            } for key in all_keys]
            return 302, orjson.dumps({
                "status": "success",
                "action": "get all",
                "pastes": all_pastes
            })


app = PasteApp()
