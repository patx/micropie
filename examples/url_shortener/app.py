# shorty_index_only.py
# URL shortener on MicroPie using ONLY the `index` method for both create & redirect.
# No middleware. Path params are mapped to `index(id=...)` automatically by MicroPie.
# Run: uvicorn shorty_index_only:app --reload

import re
import secrets
import string
from typing import Optional
from urllib.parse import urlparse

from micropie import App
from pickledb import PickleDB

# ---- storage ----
db = PickleDB("shorty.json")  # persisted JSON file

# ---- config ----
ALPHABET = string.ascii_letters + string.digits
SLUG_LEN = 6

# ---- helpers ----
def _rand_slug(n: int = SLUG_LEN) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))

def _is_valid_url(url: str) -> bool:
    """Basic URL validation."""
    if not url:
        return False
    # Simple regex for URL validation (http(s) scheme, domain, optional path)
    pattern = r'^https?://[a-zA-Z0-9-._~:/?#[\]@!$&\'()*+,;=]+[^/]$'
    return bool(re.match(pattern, url))

class Root(App):

    async def index(self, id: Optional[str] = None):
        if self.request.method == "POST":
            # Use body_params for form data instead of query_params
            url = self.request.body_params.get('url', [''])[0]
            if not _is_valid_url(url):
                return 400, "Invalid URL provided"
            slug = _rand_slug()
            while db.get(slug):
                slug = _rand_slug()
            db.set(slug, url)
            db.save()
            short = f"http://127.0.0.1:8000/{slug}"
            return f"Your short URL is <a href='{short}'>{short}</a>"
        elif self.request.method == "GET":
            if id:
                dest = db.get(id)
                if not dest:
                    return 404, "Not Found"
                # Ensure destination URL is valid before redirecting
                if not _is_valid_url(dest):
                    return 400, "Invalid destination URL"
                return self._redirect(dest)
            else:
                return (
                    """
                    <h1>Shorty</h1>
                    <form method="post" enctype="application/x-www-form-urlencoded">
                      <input type="url" name="url" placeholder="https://example.com" required style="width:28rem">
                      <button type="submit">Shorten</button>
                    </form>
                    """
                )

app = Root()
