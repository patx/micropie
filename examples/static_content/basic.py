from MicroPie import App

class Root(App):

    async def serve_static(self, path):
            file_path = os.path.join("static", path)
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, "rb") as f:
                    return await f.read(), [("Content-Type", "application/octet-stream")]
            return 404, "Not Found"

app = Root()
