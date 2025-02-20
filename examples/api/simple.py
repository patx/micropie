from MicroPie import App


class Root(App):

    async def index(self, id, name, age):
        if self.request.method == 'POST':
            return {'id': id,'name': name,'age': age}

    async def echo(self):
        data = self.request.get_json
        return {"input": data, "extra": True}

    async def example(self):
        return ["a", "b"]

    async def html(self):
        return 'Hello world'

app = Root()
