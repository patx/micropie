import os
from MicroPie import App

VIDEO_PATH = "video.mp4"

class Root(App):
    def index(self):
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

    async def stream(self):
        # Access the request headers using the self.request property
        headers = {
            k.decode('latin-1').lower(): v.decode('latin-1')
            for k, v in self.request.scope.get('headers', [])
        }
        range_header = headers.get('range')
        file_size = os.path.getsize(VIDEO_PATH)

        # Decide on start/end
        start, end = 0, file_size - 1
        status_code = 200
        extra_headers = [
            ("Accept-Ranges", "bytes"),
            ("Content-Type", "video/mp4"),
        ]

        if range_header:
            # e.g. "bytes=1234-" or "bytes=1234-5678"
            try:
                byte_range = range_header.replace("bytes=", "")
                start_str, end_str = byte_range.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                if start >= file_size or end >= file_size:
                    start, end = 0, file_size - 1

                content_length = end - start + 1
                extra_headers += [
                    ("Content-Range", f"bytes {start}-{end}/{file_size}"),
                    ("Content-Length", str(content_length)),
                ]
                status_code = 206
            except ValueError:
                # Malformed range; fallback
                pass
        else:
            # Full content
            extra_headers.append(("Content-Length", str(file_size)))

        # Make an async generator that yields file chunks
        async def file_chunk_generator(start_pos, end_pos, chunk_size=1024 * 1024):
            with open(VIDEO_PATH, "rb") as f:
                f.seek(start_pos)
                remaining = (end_pos + 1) - start_pos
                while remaining > 0:
                    data = f.read(min(chunk_size, remaining))
                    if not data:
                        break
                    yield data
                    remaining -= len(data)

        return (status_code, file_chunk_generator(start, end), extra_headers)

app = Root()
