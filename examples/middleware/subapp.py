from micropie import App, HttpMiddleware, Request

# Define the Sub-App
class ApiApp(App):
    async def index(self):
        return {"message": "Welcome to the API!"}

    async def users(self, user_id: str):
        return {"user_id": user_id, "message": f"User {user_id} from API"}

# Define a Middleware to Mount the Sub-App
class SubAppMiddleware(HttpMiddleware):
    def __init__(self, mount_path: str, subapp: App):
        self.mount_path = mount_path.lstrip("/")
        self.subapp = subapp

    async def before_request(self, request):
        path = request.scope["path"].lstrip("/")
        if path.startswith(self.mount_path):
            # Set the subapp and the remaining path
            request._subapp = self.subapp
            request._subapp_path = path[len(self.mount_path):].lstrip("/") or "/"
            return None  # Continue processing
        return None  # Not a subapp path, continue with main app

    async def after_request(
        self, request, status_code, response_body, extra_headers):
        return None  # No changes to response

# Define the Main App
class MainApp(App):
    async def index(self):
        return {"message": "Welcome to the Main App!"}

    async def hello(self, name: str):
        return {"message": f"Hello, {name} from Main App!"}

# Create and Configure the Apps
app = MainApp()
api_app = ApiApp()

# Mount the sub-app at /api
subapp_middleware = SubAppMiddleware(mount_path="/api", subapp=api_app)
app.middlewares.append(subapp_middleware)
