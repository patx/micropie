from micropie import App


class Root(App):

    async def index(self, id, name, age):
        if self.request.method == "POST":
            return {"id": id,"name": name,"age": age}

    async def echo(self):
        if self.request.method == "GET":
            return {"input": False, "extra": False}

        data = self.request.get_json
        return {"input": data, "extra": True}

    async def example(self):
        return ["a", "b"]

    async def html(self):
        return "<b>Hello world</b>"

app = Root()
