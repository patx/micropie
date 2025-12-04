"""
myapp_motor, a minimal example using Motor (MongoDB) as the session backend
with MicroPie.

This application increments a visit counter stored in a MongoDB collection for sessions.
"""

from micropie import App, SessionBackend, SESSION_TIMEOUT
import motor.motor_asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any


class MotorSessionBackend(SessionBackend):
    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        collection_name: str = "sessions",
        default_timeout: int = SESSION_TIMEOUT,
    ) -> None:
        """
        A simple MongoDB-backed session store for MicroPie using Motor.

        NOTE:
        - Suitable for real deployments as a starting point.
        - You should still tune indexes, replica set, etc. for your environment.
        """
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.default_timeout = default_timeout

    async def load(self, session_id: str) -> Dict[str, Any]:
        """
        Load session data from MongoDB.

        - If no session_id is provided, returns an empty dict.
        - If the session is expired, deletes it and returns empty.
        """
        if not session_id:
            return {}

        doc = await self.collection.find_one({"_id": session_id})
        if not doc:
            return {}

        expires_at = doc.get("expires_at")
        if expires_at is not None and datetime.utcnow() > expires_at:
            # Expired: clean up and treat as no session
            await self.collection.delete_one({"_id": session_id})
            return {}

        return doc.get("data", {}) or {}

    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        """
        Save session data into MongoDB with an expiration time.

        MicroPie may call this with:
        - `data` empty and/or `timeout <= 0` to mean "delete this session".
        """
        if not session_id:
            # If we somehow got here with an empty session_id, just ignore.
            return

        # Treat empty data or non-positive timeout as a delete / logout
        if not data or timeout <= 0:
            await self.collection.delete_one({"_id": session_id})
            return

        # Use the timeout provided by MicroPie if set, otherwise our default.
        ttl = timeout or self.default_timeout
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        await self.collection.update_one(
            {"_id": session_id},
            {"$set": {"data": data, "expires_at": expires_at}},
            upsert=True,
        )


class MyApp(App):
    async def index(self):
        # Access the session via self.request.session.
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1

        return f"You have visited {self.request.session['visits']} times."


# MongoDB configuration; adjust the URI and database name as needed.
MONGO_URI = "your uri here"
DB_NAME = "example"

# Create an instance of the Motor session backend.
backend = MotorSessionBackend(MONGO_URI, DB_NAME)

# Pass the Motor session backend to our application.
app = MyApp(session_backend=backend)

