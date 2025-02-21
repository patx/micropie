from MicroPie import App
import requests
import os

# GitHub OAuth settings
CLIENT_ID = "your client id"
CLIENT_SECRET = "your client secret"
REDIRECT_URI = "http://0.0.0.0:8000/callback"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com/user"

class Root(App):
    async def index(self):
        return '<a href="/login">Login with GitHub</a>'

    async def login(self):
        return self._redirect(f"{GITHUB_AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}")

    async def callback(self):
        code = self.request.query_params.get("code")
        if not code:
            return "Error: No code provided"

        # Exchange code for access token
        response = requests.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )
        data = response.json()
        access_token = data.get("access_token")

        if not access_token:
            return "Error: Could not get access token"

        # Fetch user data from GitHub API
        user_data = requests.get(
            GITHUB_API_URL, headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        return f"Hello, {user_data.get('login')}! <br><img src='{user_data.get('avatar_url')}' width='100'>"


app = Root()
