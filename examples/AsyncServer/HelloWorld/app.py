from MicroPie import AsyncServer


class Root(AsyncServer):

    async def index(self):
        return 'Hello ASGI World!'

    async def hello(self, name="ASGI"):
        return f'Hello {name}!'

app = Root() #  Run with `uvicorn app:app`
