from MicroPie import Server
import os, uuid


class Root(Server):

    def upload_file(self, file):
        """
        Handler function to process uploaded files.

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

        # Sanitize the filename to prevent directory traversal attacks
        filename = os.path.basename(filename)

        # Optionally, generate a unique filename to prevent overwriting
        unique_filename = f"{uuid.uuid4()}_{filename}"
        upload_path = os.path.join(upload_dir, unique_filename)

        try:
            with open(upload_path, 'wb') as f:
                f.write(data)
        except IOError as e:
            return 500, f"Failed to save file: {str(e)}"

        return 200, f"""File '{filename}' uploaded successfully as '{unique_filename}'. <a href="/">Upload another</a>"""

    # Example Index Handler to Render Upload Form
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
