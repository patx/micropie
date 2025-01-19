from MicroPie import Server

class MyApp(Server):
    def index(self, name="Guest"):
        return f"Hello, {name}! Welcome to MicroPie."

# Create an instance of the app
app = MyApp()
