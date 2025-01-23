import os
from MicroPie import Server

VIDEO_PATH = "path/to/your/video.mp4"

class VideoStreamer(Server):
    def index(self):
        """Serve the HTML page with a video player."""
        return '''
        <html>
        <body>
          <center>
            <video width="640" height="360" controls>
                <source src="/stream" type="video/mp4">
                Your browser does not support the video tag.
            </video>
          </center>
        </body>
        </html>
        '''

    def stream(self):
        """Stream the video file in chunks."""
        def generator():
            chunk_size = 1024 * 1024  # 1MB chunks
            try:
                with open(VIDEO_PATH, 'rb') as video:
                    while chunk := video.read(chunk_size):
                        yield chunk
            except FileNotFoundError:
                yield b"Video file not found."

        return generator()

app = VideoStreamer()
wsgi_app = app.wsgi_app
