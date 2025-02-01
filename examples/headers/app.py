from MicroPie import Server


class Root(Server):
    def index(self):
        # Simply return the precomputed response
        return self._response
    def __init__(self):
        # Precompute the headers once during initialization
        self._headers = [
            ("Content-Type", "text/html"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("X-XSS-Protection", "1; mode=block"),
            ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
            ("Content-Security-Policy", "default-src 'self'")
        ]
        self._response = (200, "<b>hello world</b>", self._headers)



app = Root()
