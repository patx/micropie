import os
import re
import aiofiles
from MicroPie import App

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure directory exists
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

class Root(App):

    async def index(self):
        return """<form action="/upload" method="post" enctype="multipart/form-data">
            <label for="file">Choose a file:</label>
            <input type="file" id="file" name="file" required>
            <input type="submit" value="Upload">
        </form>"""

    async def upload(self, file):
        try:
            filename = file["filename"]
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
            queue = file["content"]
            total_bytes = 0
            filepath = os.path.join(UPLOAD_DIR, safe_filename)

            async with aiofiles.open(filepath, "wb") as f:
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    if total_bytes + len(chunk) > MAX_UPLOAD_SIZE:
                        await aiofiles.os.remove(filepath)  # Clean up partial file
                        return 400, "File exceeds maximum size of 100MB"
                    await f.write(chunk)
                    total_bytes += len(chunk)

            return 200, f"Uploaded {safe_filename} ({total_bytes} bytes) to {filepath}"
        except Exception as e:
            print(f"Upload error: {e}")
            return 500, f"Failed to upload {filename}: {str(e)}"

app = Root()
