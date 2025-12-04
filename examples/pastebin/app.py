from micropie import App
import dataset

db = dataset.connect('sqlite:///pastes.db')
pastes = db['pastes']


class Root(App):

    async def index(self, paste_content=None):
        if self.request.method == 'POST':
            new_id = pastes.insert({'content': paste_content})
            return self._redirect(f'/paste/{new_id}')
        return await self._render_template('index.html')

    async def paste(self, paste_id, delete=None):
        if delete == 'delete':
            pastes.delete(id=paste_id)
            return self._redirect('/')

        paste = pastes.find_one(id=paste_id)
        if not paste:
            paste = {'content':404}

        return await self._render_template(
            'paste.html',
            paste_id=paste_id,
            paste_content=paste['content'],
        )


app = Root()
