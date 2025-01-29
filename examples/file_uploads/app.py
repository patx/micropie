from MicroPie import Server
import os, uuid, asyncio


class Root(Server):

    async def save_file_async(self, upload_path, data):
        """
        Asynchronously writes file data to the specified path.
        """
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._write_file, upload_path, data)
        except IOError as e:
            return 500, f"Failed to save file: {str(e)}"
        return 200, f"File uploaded successfully as '{os.path.basename(upload_path)}'. <a href='/'>Upload another</a>"

    def _write_file(self, upload_path, data):
        """
        Synchronous function to write data to a file.
        Used with run_in_executor to avoid blocking the event loop.
        """
        with open(upload_path, 'wb') as f:
            f.write(data)

    async def upload_file(self, file):
        """
        Asynchronous handler function to process uploaded files.

        Parameters:
        - file: A dictionary containing 'filename', 'content_type', and 'data'.
        """
        if not file:
            return 400, "No file uploaded."

        filename = file['filename']
        content_type = file['content_type']
        data = file['data']

        # Ensure the 'uploads' directory exists
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)

        # Sanitize and create a unique filename
        filename = os.path.basename(filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        upload_path = os.path.join(upload_dir, unique_filename)

        # Asynchronously save the file
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

