from micropie import HttpMiddleware

class SubAppMiddleware(HttpMiddleware):
    def __init__(self, mount_path: str, subapp):
        self.mount_path = mount_path.lstrip("/")
        self.subapp = subapp

    async def before_request(self, request):
        path = request.scope["path"].lstrip("/")
        if path.startswith(self.mount_path):
            request._subapp = self.subapp
            request._subapp_path = path[len(self.mount_path):].lstrip("/") or "/"
            request._subapp_mount_path = self.mount_path
        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        return None

