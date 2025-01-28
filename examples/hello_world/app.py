from MicroPie import Server


class Root(Server):

    def index(self, name=None):
        if name:
            return f'Hello {name}'
        return 'Hello ASGI World!'

app = Root() #  Run with `uvicorn app:app`
