import time

from MicroPie import App, HttpMiddleware


class RateLimitMiddleware(HttpMiddleware):

    requests_store = {}
    RATE_LIMIT_WINDOW = 60
    MAX_REQUESTS = 10

    async def before_request(self, request):
        client_ip = request.scope.get("client")[0]
        current_time = time.time()

        if client_ip not in self.requests_store:
            self.requests_store[client_ip] = []

        self.requests_store[client_ip] = [
            req_time for req_time in self.requests_store[client_ip]
            if req_time > current_time - self.RATE_LIMIT_WINDOW
        ]

        if len(self.requests_store[client_ip]) >= self.MAX_REQUESTS:
            return {"status_code": 429, "body": f"Rate limit exceeded for IP {client_ip}.", "headers": []}

        self.requests_store[client_ip].append(current_time)
        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        pass


class MyApp(App):

    async def index(self):
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        return f"You have visited {self.request.session['visits']} times."


app = MyApp()
app.middlewares.append(RateLimitMiddleware())
