from MicroPie import App


class Root(App):

    async def new_post(self):
        data = self.request.get_json
        return {'status': 'ok', 'data': data}


app = Root()
