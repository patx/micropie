from MicroPie import App


class Root(App):

    async def index(self):
        return 'Hello ASGI World!'

app = Root() #  Run with `uvicorn app:app`
