from servestatic import ServeStaticASGI
from MicroPie import App

class Root(App):
    async def index(self):
        return "Hello, World!"

# Create the application
application = Root()

# Wrap it with ServeStaticASGI for static file serving
app = ServeStaticASGI(application, root="static")
