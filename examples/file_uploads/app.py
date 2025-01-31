from MicroPie import Server

import os
import uuid
import asyncio

UPLOAD_DIR = "uploads"
ALLOWED_FILE_TYPES = {"image/png", "image/jpeg", "application/pdf", "video/mp4"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

class Root(Server):

    async def save_file_async(self, upload_path, data):
        """
        Asynchronously writes file data to the specified path in chunks.
        """
        loop = asyncio.get_running_loop()
        try:
            with open(upload_path, "wb") as f:
                # Stream the file in chunks (64KB each)
                chunk_size = 64 * 1024
                for i in range(0, len(data), chunk_size):
                    chunk = data[i : i + chunk_size]
                    await loop.run_in_executor(None, f.write, chunk)
        except IOError as e:
            return 500, f"Failed to save file: {str(e)}"
        return f"File uploaded successfully as '{os.path.basename(upload_path)}'. <a href='/'>Upload another</a>"

    async def upload_file(self):
        """
        Handles file upload securely and streams it to disk.
        """
        request = self.request  # Access the current request from MicroPie
        if "file" not in request.files:
            return 400, "No file uploaded."

        file = request.files["file"]
        filename = os.path.basename(file["filename"])
        content_type = file["content_type"]
        data = file["data"]

        # Security check: Validate file type
        if content_type not in ALLOWED_FILE_TYPES:
            return 400, f"Invalid file type: {content_type}. Allowed types: {', '.join(ALLOWED_FILE_TYPES)}"

        # Check file size
        if len(data) > MAX_FILE_SIZE:
            return 400, f"File too large! Maximum allowed size is {MAX_FILE_SIZE / (1024 * 1024)} MB."

        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}_{filename}"
        upload_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Stream file data to disk in chunks
        return await self.save_file_async(upload_path, data)

    def index(self):
        """
        Render a simple HTML form for file uploads.
        """
        return (
            "<!DOCTYPE html>"
            "<html>"
            "<head><title>Upload File</title></head>"
            "<body>"
            "<h1>Upload a File</h1>"
            "<form action='/upload_file' method='post' enctype='multipart/form-data'>"
            "<input type='file' name='file' required>"
            "<button type='submit'>Upload</button>"
            "</form>"
            "</body>"
            "</html>"
        )

app = Root()
