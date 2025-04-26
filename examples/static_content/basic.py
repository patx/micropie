from MicroPie import App
import os
import aiofiles
import mimetypes

class Root(App):

    async def static(self, path):
        # Normalize the file path to prevent directory traversal
        file_path = os.path.normpath(os.path.join("static", path))
        # Ensure the path stays within the 'static' directory
        static_dir = os.path.normpath("static")
        if not file_path.startswith(static_dir):
            return 403, "Forbidden", []

        if os.path.exists(file_path):
            # Determine the appropriate Content-Type based on file extension
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            # Stream the file content to reduce memory usage
            async def stream_file():
                async with aiofiles.open(file_path, "rb") as f:
                    while chunk := await f.read(65536):  # Read in 64KB chunks
                        yield chunk

            return 200, stream_file(), [("Content-Type", content_type)]
        return 404, "Not Found", []

app = Root()
