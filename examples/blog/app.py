from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import markdown
from micropie import App
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from middlewares.rate_limit import MongoRateLimitMiddleware
from sessions.mongo_session import MkvSessionBackend


MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "blogdb"
COLLECTION_POSTS = "posts"
COLLECTION_USERS = "users"
USERNAME = "demo"
FULLNAME = "John Smith"

def serialize_post(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Mongo document into a JSON-friendly dict."""
    created_at = doc.get("created_at")
    if isinstance(created_at, datetime):
        created_at_str = created_at.replace(microsecond=0).isoformat() + "Z"
    else:
        created_at_str = str(created_at) if created_at is not None else ""

    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title", ""),
        "content": doc.get("content", ""),
        "created_at": created_at_str,
        "author_username": doc.get("author_username"),
    }


# ---------- Startup / shutdown ----------

async def init_db():
    try:
        print("[init_db] starting init")
        app.mongo_client = AsyncIOMotorClient(MONGO_URI)
        app.db = app.mongo_client[DB_NAME]
        app.posts = app.db[COLLECTION_POSTS]
        app.users = app.db[COLLECTION_USERS]

        # sanity ping
        await app.db.command("ping")
        print("[init_db] mongo ping OK")

        await app.posts.create_index([("created_at", -1)])
        await app.users.create_index("username", unique=True)

        existing = await app.users.find_one({"username": USERNAME})
        if not existing:
            await app.users.insert_one(
                {"username": "demo", "password": "demo"}
            )

        print("[init_db] finished without error")

    except Exception as e:
        import traceback
        print("[init_db] ERROR!", repr(e))
        traceback.print_exc()
        raise

async def close_db():
    """
    ASGI shutdown handler: close Mongo client.
    """
    app.mongo_client.close()


class BlogApp(App):
    # ---------- Helpers ----------

    def _current_user_id(self) -> Optional[str]:
        """
        Return current user_id from session, or None.
        """
        sess = getattr(self.request, "session", None)
        if not sess:
            return None
        return sess.get("user_id")

    async def _get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Look up user document for current session user_id.
        """
        user_id = self._current_user_id()
        if not user_id:
            return None

        try:
            oid = ObjectId(user_id)
        except Exception:
            return None

        return await self.users.find_one({"_id": oid})

    def _require_login_redirect(self, next_path: str = "/"):
        """
        For HTML endpoints: if not logged in, redirect to /login?next=...
        """
        if not self._current_user_id():
            return self._redirect(f"/login?next={next_path}")
        return None

    def _require_login_json(self):
        """
        For JSON endpoints: return (status, body) 401 if not logged in.
        """
        if not self._current_user_id():
            return 401, {"error": "Authentication required."}
        return None

    # ---------- HTML HANDLERS ----------

    async def index(self):
        """
        HTML: List all posts on the home page (/).
        """
        posts_cursor = self.posts.find(
            {},
            projection={"title": 1, "created_at": 1},
        ).sort("created_at", -1)

        posts: List[Dict[str, Any]] = []
        async for doc in posts_cursor:
            p = serialize_post(doc)
            posts.append(
                {
                    "id": p["id"],
                    "title": p["title"],
                    "created_at": p["created_at"],
                }
            )

        user = await self._get_current_user()
        return await self._render_template(
            "index.html",
            title="My MicroPie Blog",
            posts=posts,
            current_user=user,
            request=self.request,
            nav_active="index",
        )

    async def post(self, id):
        """
        HTML: Show a single post at /post/<id>.
        """
        try:
            oid = ObjectId(id)
        except Exception:
            return 404, "Post not found"

        doc = await self.posts.find_one({"_id": oid})
        if not doc:
            return 404, "Post not found"

        post = serialize_post(doc)
        user = await self._get_current_user()

        html = markdown.markdown(post["content"])
        return await self._render_template(
            "post.html",
            title=post["title"],
            post=post,
            post_html=html,
            current_user=user,
            request=self.request,
            nav_active="index",
        )

    async def new(self):
        """
        HTML: Create new post at /new.
        - GET → show form (only if logged in)
        """
        guard = self._require_login_redirect(next_path="/new")
        if guard is not None:
            return guard  # redirect to /login

        if self.request.method == "GET":
            user = await self._get_current_user()
            return await self._render_template(
                "new.html",
                title="New Post",
                error=None,
                current_user=user,
                request=self.request,
                nav_active="new",
            )

    async def login(self):
        """
        HTML: /login

        GET  → show login form
        POST → authenticate and set session, then redirect
        """
        next_path = self.request.query_params.get("next", ["/"])[0]

        if self.request.method == "GET":
            return await self._render_template(
                "login.html",
                title="Login",
                error=None,
                next_path=next_path,
                request=self.request,
                nav_active="login",
            )

        username = self.request.body_params.get("username", [""])[0].strip()
        password = self.request.body_params.get("password", [""])[0].strip()

        user = await self.users.find_one({"username": username})
        if not user or user.get("password") != password:
            return await self._render_template(
                "login.html",
                title="Login",
                error="Invalid username or password.",
                next_path=next_path,
                request=self.request,
                nav_active="login",
            )

        self.request.session["user_id"] = str(user["_id"])
        return self._redirect(next_path)

    async def logout(self):
        """
        HTML: /logout — clear session and redirect home.
        """
        if hasattr(self.request, "session"):
            self.request.session.clear()
        return self._redirect("/")


    # ---------- JSON API HANDLERS ----------

    async def api_posts(self):
        """
        JSON: /api_posts

        - GET  → list posts
        - POST → create post (requires login)
        """
        if self.request.method == "GET":
            cursor = self.posts.find({}).sort("created_at", -1)
            posts = [serialize_post(doc) async for doc in cursor]
            return {"posts": posts}

        if self.request.method == "POST":
            guard = self._require_login_json()
            if guard is not None:
                return guard

            try:
                data = self.request.get_json
            except Exception:
                return 400, {"error": "Invalid JSON payload."}

            title = str(data.get("title", "")).strip()
            content = str(data.get("content", "")).strip()

            if not title or not content:
                return 400, {"error": "title and content are required."}

            user = await self._get_current_user()
            user_id = str(user["_id"]) if user else None
            username = user.get("username") if user else None

            doc = {
                "title": title,
                "content": content,
                "created_at": datetime.utcnow(),
                "author_id": user_id,
                "author_username": username,
            }
            result = await self.posts.insert_one(doc)
            created = await self.posts.find_one({"_id": result.inserted_id})

            return 201, serialize_post(created)

        return 405, {"error": "Method not allowed on /api_posts."}

    async def api_post(self, id):
        """
        JSON: /api_post/<id>

        - GET    → fetch single post
        - PATCH  → partially update post (requires login)
        - PUT    → update post (same semantics here as PATCH)
        - DELETE → delete post (requires login)
        """
        try:
            oid = ObjectId(id)
        except Exception:
            return 400, {"error": "Invalid post id."}

        doc = await self.posts.find_one({"_id": oid})
        if not doc:
            return 404, {"error": "Post not found."}

        if self.request.method == "GET":
            post = serialize_post(doc)
            post["html"] = markdown.markdown(post["content"])
            return post

        if self.request.method in ("PATCH", "PUT"):
            guard = self._require_login_json()
            if guard is not None:
                return guard

            try:
                data = self.request.get_json
            except Exception:
                return 400, {"error": "Invalid JSON payload."}

            updates: Dict[str, Any] = {}

            if "title" in data:
                title = str(data["title"]).strip()
                if not title:
                    return 400, {"error": "title cannot be empty."}
                updates["title"] = title

            if "content" in data:
                content = str(data["content"]).strip()
                if not content:
                    return 400, {"error": "content cannot be empty."}
                updates["content"] = content

            if not updates:
                return 400, {"error": "Nothing to update."}

            updates["updated_at"] = datetime.utcnow()

            await self.posts.update_one({"_id": oid}, {"$set": updates})
            updated = await self.posts.find_one({"_id": oid})
            post = serialize_post(updated)
            post["html"] = markdown.markdown(post["content"])
            return post

        if self.request.method == "DELETE":
            guard = self._require_login_json()
            if guard is not None:
                return guard

            await self.posts.delete_one({"_id": oid})
            return {"ok": True}

        return 405, {"error": "Method not allowed on /api_post/<id>."}



app = BlogApp(session_backend=MkvSessionBackend(
    mongo_uri=MONGO_URI, 
    db_name=DB_NAME
    )
)
app.middlewares.append(
    MongoRateLimitMiddleware(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        allowed_hosts=None,          # don't enforce host allowlist, change in prod
        trust_proxy_headers=False,   # change in prod
        require_cf_ray=False,
    )
)
app.startup_handlers.append(init_db)
app.shutdown_handlers.append(close_db)
