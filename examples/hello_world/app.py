from MicroPie import App


class Root(App):

    async def index(self):
        data = self.path_params[0]
        return 'Hello ASGI World! {data}'

    async def greet(self,first_name='World', last_name=None):
        if last_name:
            return f'Hello {first_name} {last_name}'
        return f'Hello {first_name}'

app = Root() #  Run with `uvicorn app:app`
