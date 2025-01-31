from MicroPie import Server


class Root(Server):

    async def index(self):
        return 'Hello ASGI World!'

app = Root() #  Run with `uvicorn app:app`
