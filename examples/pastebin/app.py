from uuid import uuid4
import asyncio
from MicroPie import App
from markupsafe import escape
from pickledb import AsyncPickleDB

db = AsyncPickleDB('pastes.json')


class Root(App):

    async def index(self):
        if self.request.method == "POST":
            paste_content = self.request.body_params.get('paste_content', [''])[0]
            pid = str(uuid4())
            await db.aset(pid, escape(paste_content))
            await db.asave()
            return self._redirect(f'/paste/{pid}')
        return await self._render_template('index.html')

    async def paste(self, paste_id, delete=None):
        if delete == 'delete':
            await db.aremove(paste_id)
            await db.asave()
            return self._redirect('/')
        paste_content = await db.aget(paste_id)
        return await self._render_template(
            'paste.html',
            paste_id=paste_id,
            paste_content=paste_content
        )

app = Root()
