from MicroPie import Server

class Root(Server):
    async def index(self):
        return f'Hello World!'

app = Root()
