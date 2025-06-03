import asyncio
import random
from MicroPie import App


class MyApp(App):

    async def index(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Server-Sent Events Demo with MicroPie</title>
        </head>
        <body>
            <h1>Server-Sent Events with MicroPie</h1>
            <div id="output"></div>
            <script>
                const source = new EventSource('/events');
                source.onmessage = function(event) {
                    const newElement = document.createElement("p");
                    newElement.textContent = `Received: ${event.data}`;
                    document.getElementById("output").appendChild(newElement);
                };
                source.onerror = function() {
                    console.log("SSE error occurred");
                };
            </script>
        </body>
        </html>
        """

    # SSE endpoint to stream random numbers
    async def events(self):
        async def event_generator():
            try:
                while True:
                    # Generate random number
                    data = f"Random number: {random.randint(1, 100)}"
                    # Yield SSE formatted data
                    yield f"data: {data}\n\n".encode("utf-8")
                    # Wait for 1 second before sending next event
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                print("Client disconnected")
                raise

        # Return status code, async generator, and headers for SSE
        return 200, event_generator(), [("Content-Type", "text/event-stream")]

app = MyApp()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
