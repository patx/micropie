from MicroPie import Server

import os
from typing import Any

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure upload directory exists

class FileUploadApp(Server):

    async def index(self):
        """Serves an HTML form for file uploads."""
        return """<html>
            <head><title>File Upload</title></head>
            <body>
                <h2>Upload a File</h2>
                <form action="/upload" method="post" enctype="multipart/form-data">
                    <input type="file" name="file"><br><br>
                    <input type="submit" value="Upload">
                </form>
            </body>
        </html>"""

    async def upload(self, file: Any):
        """Handles file uploads."""
        if isinstance(file, dict) and "filename" in file and "data" in file:
            filename = file["filename"]
            file_data = file["data"]

            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(file_data)

            return f"File '{filename}' uploaded successfully!"
        return "No file uploaded.", 400

# Run the ASGI app
app = FileUploadApp()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

