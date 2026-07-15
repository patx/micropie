"""Configure upload limits before MicroPie's HTTP middleware layer."""

from micropie import App

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB


class FileUploadApp(App):
    async def index(self):
        """Serves an HTML form for file uploads."""
        return (
            200,
            """<html>
<head><title>File Upload</title></head>
<body>
    <h2>Upload a File</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file"><br><br>
        <input type="submit" value="Upload">
    </form>
</body>
</html>""",
            [("Content-Type", "text/html; charset=utf-8")],
        )

    async def upload(self, file):
        """Handles file uploads and processes the file content."""
        filename = file["filename"]
        content_type = file["content_type"]
        content_queue = file["content"]

        # Process file content from the queue
        total_size = 0
        while True:
            chunk = await content_queue.get()
            if chunk is None:  # End of file
                break
            total_size += len(chunk)
            # Example: Process chunk (e.g., save to disk, validate, etc.)
            # For demonstration, just count the size
        return {"filename": filename, "content_type": content_type, "size": total_size}


app = FileUploadApp(max_body_size=MAX_UPLOAD_SIZE)
