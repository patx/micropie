from servestatic import ServeStaticASGI
from MicroPie import Server

class Root(Server):
    async def index(self):
        return "Hello, World!"

# Create the application
app = Root()

# Wrap it with ServeStaticASGI for static file serving
app = ServeStaticASGI(application, root="static")
