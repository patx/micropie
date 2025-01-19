# Guide: Running MicroPie with WebSockets

This guide explains how to run the **MicroPie** framework alongside a WebSocket server using Python's `asyncio` and `websockets` libraries.


## **1. Overview**

The provided script runs a MicroPie web application while simultaneously hosting a WebSocket server on a different port. The WebSocket server runs in a separate thread to enable concurrent handling of HTTP and WebSocket traffic.

### **Key Components:**
- MicroPie web server handling HTTP requests on port `8080`.
- WebSocket server handling WebSocket connections on port `8765`.


## **2. Prerequisites**

Ensure you have Python installed along with the required dependencies:

```bash
pip install micropie websockets
```


## **3. Code Explanation**

### **`server.py` (Main Script)**

```python
import threading
import asyncio
import websockets
from MicroPie import Server

class MyApp(Server):
    def index(self):
        return "WebSocket available at ws://localhost:8765"

def start_websocket_server():
    async def echo(websocket, path):
        async for message in websocket:
            await websocket.send(f"Echo: {message}")

    asyncio.run(websockets.serve(echo, "localhost", 8765))
    asyncio.get_event_loop().run_forever()

# Run MicroPie in the main thread
if __name__ == "__main__":
    threading.Thread(target=start_websocket_server, daemon=True).start()
    MyApp().run()
```

### **Explanation:**
1. **MicroPie Web Server (`MyApp`)**
   - Handles HTTP requests and serves content on `http://localhost:8080`.
   - Displays a message indicating WebSocket availability.

2. **WebSocket Server (`start_websocket_server`)**
   - Listens on `ws://localhost:8765`.
   - Handles incoming WebSocket messages and echoes them back to the client.

3. **Threading:**
   - The WebSocket server runs in a separate daemon thread, allowing the HTTP server to run concurrently.


## **4. Running the Application**

Run the script with:

```bash
python server.py
```

- The HTTP server will be available at `http://localhost:8080`.
- The WebSocket server will be accessible at `ws://localhost:8765`.


## **5. Testing the WebSocket Server**

You can test the WebSocket server using a simple Python script or browser console.

### **Python WebSocket Client Test:**

```python
import asyncio
import websockets

async def test_websocket():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello, Server!")
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())
```

### **JavaScript WebSocket Test (Browser Console):**

```javascript
let socket = new WebSocket("ws://localhost:8765");

socket.onopen = function() {
    console.log("Connected to WebSocket server");
    socket.send("Hello from client!");
};

socket.onmessage = function(event) {
    console.log("Received from server:", event.data);
};
```


## **6. Stopping the Application**

To stop the running application, use:

```bash
CTRL + C
```

## **7. Deploying the Application**

For production, consider running the application with **Gunicorn** or Docker:

### **Using Gunicorn:**

```bash
gunicorn -w 4 -b 0.0.0.0:8080 server:MyApp
```

### **Using Docker:**

Create a `Dockerfile`:

```dockerfile
FROM python:3.9
WORKDIR /app
COPY server.py .
RUN pip install micropie websockets
CMD ["python", "server.py"]
```

Build and run:

```bash
docker build -t micropie-websocket .
docker run -p 8080:8080 -p 8765:8765 micropie-websocket
```

## **8. Conclusion**

This guide covered how to run MicroPie with a WebSocket server simultaneously, allowing HTTP and WebSocket communication within the same application. This setup is useful for applications requiring real-time capabilities such as chat applications, notifications, or live updates.

---

For further questions, feel free to reach out or explore additional integrations with databases and authentication services.


