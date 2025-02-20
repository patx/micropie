from MicroPie import App
import json


class Root(App):

    async def index(self, id, name, age, zip):
        if self.request.method == 'POST':
            result = {'id': id,'name': name,'age': age,'zip': zip}
            return json.dumps(result)

app = Root()
