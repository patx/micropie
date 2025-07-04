from micropie import App, HttpMiddleware

class MiddlewareExample(HttpMiddleware):
    async def before_request(self, request):
        print("Hook before request")

    async def after_request(self, request, status_code, response_body, extra_headers):
        print("Hook after request")

class Root(App):
    async def index(self):
        print("Hello, World!")
        return "Hello, World!"

app = Root()
app.middlewares.append(MiddlewareExample())
