from MicroPie import App


class Root(App):

    async def index(self):
        return 'Hello ASGI World!'

    async def greet(self, first_name='World', last_name=None):
        if last_name:
            return f'Hello {first_name} {last_name}'
        return f'Hello {first_name}'

app = Root() #  Run with `uvicorn app:app`
