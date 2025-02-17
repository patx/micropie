import time
import logging
from typing import Any, Optional
from MicroPie import App, HttpMiddleware, Request

logging.basicConfig(level=logging.INFO)

class RateLimitMiddleware(HttpMiddleware):
    requests_store = {}
    RATE_LIMIT_WINDOW = 60  # seconds
    MAX_REQUESTS = 10       # allowed requests in the window

    async def before_request(self, request: "Request") -> Optional[Any]:
        client_info = request.scope.get("client")
        if client_info and isinstance(client_info, tuple):
            client_ip = client_info[0]
        else:
            client_ip = "unknown"

        current_time = time.time()

        # Initialize this IP if not present
        if client_ip not in self.requests_store:
            self.requests_store[client_ip] = []

        # Prune old timestamps outside the limit window
        self.requests_store[client_ip] = [
            req_time for req_time in self.requests_store[client_ip]
            if req_time > current_time - self.RATE_LIMIT_WINDOW
        ]

        # Log current data for debugging
        logging.info(f"[RateLimit] IP: {client_ip}")
        logging.info(f"[RateLimit] Current timestamps for {client_ip}: {self.requests_store[client_ip]}")

        # Check if limit is reached
        if len(self.requests_store[client_ip]) >= self.MAX_REQUESTS:
            logging.warning(f"[RateLimit] IP {client_ip} exceeded the rate limit.")
            return {
                "status_code": 429,
                "body": f"Rate limit exceeded for IP {client_ip}.",
                "headers": []
            }

        # Record timestamp of current request
        self.requests_store[client_ip].append(current_time)
        logging.info(f"[RateLimit] Recorded new request for IP {client_ip}.")
        return None

    async def after_request(self, request: "Request", status_code: int, response_body: Any, extra_headers: list) -> None:
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

