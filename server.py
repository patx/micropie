from micropie import App


class Root(App):

    async def index(self):
        return ""

    async def user(self, user_id=None):
        if self.request.method == "POST":
            return ""
        return user_id


app = Root()
