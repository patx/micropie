import os
from MicroPie import Server

VIDEO_PATH = "video.mp4"


class VideoStreamer(Server):

    def index(self):
        """Serve a simple HTML page with a video player."""
        return '''
            <html>
            <body>
            <center>
                <video width="640" height="360" controls>
                    <source src="/stream" type="video/mp4">
                    Your browser does not support the video tag. Use Chrome for best results.
                </video>
            </center>
            </body>
            </html>
        '''

    def stream(self):
        """
        Stream the video file with support for range requests (seeking).
        This will only work in WSGI mode, because the built-in server in
        MicroPie doesn't handle custom headers for partial-content.
        """
        environ = self.environ  # Provided by our updated MicroPie
        range_header = environ.get('HTTP_RANGE')
        file_size = os.path.getsize(VIDEO_PATH)

        def generator(start=0, end=None):
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(VIDEO_PATH, 'rb') as video:
                video.seek(start)
                remaining = end - start if end else file_size - start
                while remaining > 0:
                    data = video.read(min(chunk_size, remaining))
                    if not data:
                        break
                    yield data
                    remaining -= len(data)

        if range_header:
            try:
                # Example "Range" header: "bytes=1234-"
                # or "bytes=1234-5678"
                range_value = range_header.replace('bytes=', '')
                start_str, end_str = range_value.split('-')
                start = int(start_str)
                end = int(end_str) if end_str else file_size - 1

                # Ensure range is within file bounds
                if start >= file_size or end >= file_size:
                    start, end = 0, file_size - 1

                content_length = end - start + 1

                # Return a 3-element tuple with status, body, and custom headers
                extra_headers = [
                    ("Content-Range", f"bytes {start}-{end}/{file_size}"),
                    ("Accept-Ranges", "bytes"),
                    ("Content-Length", str(content_length)),
                    ("Content-Type", "video/mp4"),
                ]
                return (206, generator(start, end + 1), extra_headers)

            except ValueError:
                # If the Range header was invalid, just fall back to full video
                pass

        # Default: return the full video
        extra_headers = [
            ("Content-Length", str(file_size)),
            ("Content-Type", "video/mp4"),
            ("Accept-Ranges", "bytes"),
        ]
        return (200, generator(0, file_size), extra_headers)




app = VideoStreamer()
wsgi_app = app.wsgi_app  # Run with `gunicorn video1:wsgi_app`
if __name__ == "__main__":
    app.run()  # Run with `python3 video1.py`
