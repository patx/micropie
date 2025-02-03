import time
import asyncio
from MicroPie import App

class Root(App):

    def index(self):
        # Normal, immediate response (non-streaming)
        return "Hello from index!"

    async def slow_stream(self):
        # Streaming response using an async generator
        async def generator():
            for i in range(1, 6):
                yield f"Chunk {i} "
                await asyncio.sleep(1)
        return generator()



app = Root()
