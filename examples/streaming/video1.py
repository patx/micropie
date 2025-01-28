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
        Return a tuple that MicroPie interprets as:
        (status_code, body, [extra_headers])
        We'll parse the Range header from scope and produce partial or full content.
        """
        headers = {
            k.decode('latin-1').lower(): v.decode('latin-1')
            for k, v in self.scope.get('headers', [])
        }

        range_header = headers.get('range')
        file_size = os.path.getsize(VIDEO_PATH)

        def read_bytes(start=0, end=None) -> bytes:
            """Synchronous read of requested byte range."""
            if end is None or end > file_size:
                end = file_size
            length = end - start
            with open(VIDEO_PATH, 'rb') as f:
                f.seek(start)
                return f.read(length)

        if range_header:
            # Typical format: "bytes=1234-" or "bytes=1234-5678"
            try:
                byte_range = range_header.replace("bytes=", "")
                start_str, end_str = byte_range.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1

                if start >= file_size or end >= file_size:
                    # Out-of-range request, fallback to full content
                    start, end = 0, file_size - 1

                content_length = (end - start) + 1
                content = read_bytes(start, end + 1)

                extra_headers = [
                    ("Content-Range", f"bytes {start}-{end}/{file_size}"),
                    ("Accept-Ranges", "bytes"),
                    ("Content-Length", str(content_length)),
                    ("Content-Type", "video/mp4"),
                ]
                return (206, content, extra_headers)

            except ValueError:
                # Malformed Range header; fallback
                pass

        # No valid Range header; return full content
        content = read_bytes(0, file_size)
        extra_headers = [
            ("Content-Length", str(file_size)),
            ("Content-Type", "video/mp4"),
            ("Accept-Ranges", "bytes"),
        ]
        return (200, content, extra_headers)


app = VideoStreamer()

