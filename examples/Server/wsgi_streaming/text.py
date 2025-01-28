import time
from MicroPie import Server

class Root(Server):

    def index(self):
        # Normal, immediate response (non-streaming)
        return "Hello from index!"

    def slow_stream(self):
        # Streaming response using a generator
        def generator():
            for i in range(1, 6):
                yield f"Chunk {i}\n"
                time.sleep(1)  # simulate slow processing or data generation
        return generator()



app = Root()
wsgi_app = app.wsgi_app  # Run with `gunicorn text:wsgi_app`
if __name__ == "__main__":
    app.run()  # Run with `python3 text.py`
