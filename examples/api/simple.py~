from MicroPie import App


class Root(App):

    async def index(self, id, name, age, zip):
        if self.request.method == 'POST':
            return {'id': id,'name': name,'age': age,'zip': zip}

app = Root()
