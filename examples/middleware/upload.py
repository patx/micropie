"""
This file demonstrates how to use a middleware to check file upload sizes
before the request body is processed by the multipart parser.
"""

from MicroPie import App, HttpMiddleware

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


class FileUploadApp(App):
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

    async def upload(self, file):
        filename = file["filename"]
        return filename


app = FileUploadApp()
app.middlewares.append(MaxUploadSizeMiddleware())
