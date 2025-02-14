"""
myapp_motor, a minimal example using Motor (MongoDB) as the session backend
with MicroPie.

This application increments a visit counter stored in a MongoDB collection for sessions.
"""

from MicroPie import App, SessionBackend
import motor.motor_asyncio
import uuid
from datetime import datetime, timedelta

class MotorSessionBackend(SessionBackend):
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str = "sessions"):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def load(self, session_id: str) -> dict:
        """Load session data from MongoDB; if expired delete and return empty."""
        doc = await self.collection.find_one({"_id": session_id})
        if not doc:
            return {}
        if "expires_at" in doc and datetime.utcnow() > doc["expires_at"]:
            await self.collection.delete_one({"_id": session_id})
            return {}
        return doc.get("data", {})

    async def save(self, session_id: str, data: dict, timeout: int) -> None:
        """Save session data into MongoDB with an expiration time."""
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)
        await self.collection.update_one(
            {"_id": session_id},
            {"$set": {"data": data, "expires_at": expires_at}},
            upsert=True
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
MONGO_URI = "YOUR URI HERE"
DB_NAME = "example"

# Create an instance of the Motor session backend.
backend = MotorSessionBackend(MONGO_URI, DB_NAME)

# Pass the Motor session backend to our application.
app = MyApp(session_backend=backend)
