import os          # Used for file path handling and directory creation
import aiofiles    # Asynchronous file I/O operations
from MicroPie import App  # Import the base App class from MicroPie

# Ensure the "uploads" directory exists; create it if it doesn't
os.makedirs("uploads", exist_ok=True)

class Root(App):
    """
    This is the main application class that inherits from MicroPie's App.
    It defines the HTTP routes and handles the logic for file uploading.
    """

    async def index(self):
        """
        Serve a simple HTML form that lets the user choose a 
        file and submit it via POST to /upload.
        """
        return """<form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" required>
            <input type="submit" value="Upload">
            </form>"""

    async def upload(self, file):
        """
        Handle the uploaded file from the client:
        - Saves the file to disk in the "uploads" directory.
        - Uses aiofiles to write the file asynchronously, in chunks.
        
        `file` is a dictionary with:
            'filename': The original filename of the uploaded file.
            'content_type': The MIME type of the file (defaults 
                to application/octet-stream).
            'content': An asyncio.Queue containing chunks of file data as 
                bytes, with a None sentinel signaling the end of the stream.
        """

        # Construct a safe path to save the uploaded file
        filepath = os.path.join("uploads", file["filename"])
        
        # Open the destination file asynchronously for writing
        async with aiofiles.open(filepath, "wb") as f:
            # Read and write the file in chunks
            while chunk := await file["content"].get():
                await f.write(chunk)

        # Return a confirmation response with the uploaded filename
        return 200, f"Uploaded {file['filename']}"

# Instantiate the app
app = Root()

