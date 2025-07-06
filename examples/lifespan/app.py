import asyncpg
from micropie import App

class MyApp(App):
    def __init__(self):
        super().__init__()  # Defaults to InMemorySessionBackend
        self.connection_pool = None
    
    async def setup_db(self):
        print("Setting up database...")
        self.connection_pool = await asyncpg.create_pool(
            user="dbuser",
            password="dbpass",
            database="hello_world",
            host="my-database",
            port=5432
        )
        print("Database setup complete!")

    async def close_db(self):
        print("Closing database...")
        if self.connection_pool:
            await self.connection_pool.close()
            self.connection_pool = None
        print("Database closed!")
        
    async def index(self):
        return "Welcome to MicroPie ASGI."

app = MyApp()
app.on_startup([app.setup_db])
app.on_shutdown([app.close_db])
