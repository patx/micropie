from uuid import uuid4
import asyncio
from MicroPie import App
from pickledb import PickleDB
from markupsafe import escape

db = PickleDB('pastes.db')
db_lock = asyncio.Lock()

class Root(App):

    async def index(self):
        if self.request.method == "POST":
            paste_content = self.request.body_params.get('paste_content', [''])[0]
            pid = str(uuid4())
            async with db_lock:
                await asyncio.to_thread(db.set, pid, escape(paste_content))
                await asyncio.to_thread(db.save)
            return self._redirect(f'/paste/{pid}')
        return await self._render_template('index.html')

    async def paste(self, paste_id, delete=None):
        if delete == 'delete':
            async with db_lock:
                await asyncio.to_thread(db.remove, paste_id)
                await asyncio.to_thread(db.save)
            return self._redirect('/')
        paste_content = db.get(paste_id)
        return await self._render_template(
            'paste.html',
            paste_id=paste_id,
            paste_content=paste_content
        )

app = Root()

