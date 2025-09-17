from micropie import App, HttpMiddleware
import asyncio

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

class MaxUploadSizeMiddleware(HttpMiddleware):
    async def before_request(self, request):
        # Check if we're dealing with a POST, PUT, or PATCH request
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            # Ensure Content-Length is present and valid
            if content_length is None:
                return {
                    "status_code": 400,
                    "body": "400 Bad Request: Missing Content-Length header"
                }
            try:
                content_length = int(content_length)
                if content_length > MAX_UPLOAD_SIZE:
                    print(f"Upload rejected: Content-Length ({content_length}) exceeds {MAX_UPLOAD_SIZE} bytes")
                    return {
                        "status_code": 413,
                        "body": "413 Payload Too Large: Uploaded file exceeds size limit."
                    }
            except ValueError:
                return {
                    "status_code": 400,
                    "body": "400 Bad Request: Invalid Content-Length header"
                }
        # Continue processing if checks pass
        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        return None


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
            [("Content-Type", "text/html; charset=utf-8")]
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
        return {
            "filename": filename,
            "content_type": content_type,
            "size": total_size
        }


app = FileUploadApp()
app.middlewares.append(MaxUploadSizeMiddleware())
