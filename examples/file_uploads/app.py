import os
import aiofiles
from MicroPie import App

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure directory exists
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB


class MaxUploadSizeMiddleware(HttpMiddleware):
    async def before_request(self, request):
        # Check if we're dealing with a POST, PUT, or PATCH request
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            # Make sure the file is not too large
            if int(content_length) > MAX_UPLOAD_SIZE:
                return {
                    "status_code": 413,
                    "body": "413 Payload Too Large: Uploaded file exceeds size limit."
                }
        # If the check passes, return None to continue processing.
        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        return None


class Root(App):

    async def index(self):
        return """<form action="/upload" method="post" enctype="multipart/form-data">
            <label for="file">Choose a file:</label>
            <input type="file" id="file" name="file" required>
            <input type="submit" value="Upload">
        </form>"""

    async def upload(self, file):
        filename = file["filename"]
        queue = file["content"]
        total_bytes = 0
        filepath = os.path.join(UPLOAD_DIR, filename)

        async with aiofiles.open(filepath, "wb") as f:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                await f.write(chunk)
                total_bytes += len(chunk)

        return 200, f"Uploaded {filename} ({total_bytes} bytes) to {filepath}"


app = Root()

