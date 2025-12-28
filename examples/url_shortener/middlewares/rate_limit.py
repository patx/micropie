from __future__ import annotations

from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from micropie import HttpMiddleware


class MongoRateLimitMiddleware(HttpMiddleware):
    """
    Global MongoDB-based rate limiter.
    """

    MAX_REQUESTS = 50
    WINDOW_SECONDS = 60

    BLOCK_AFTER_VIOLATIONS = 3
    BLOCK_FOR_SECONDS = 900

    PERMA_WINDOW_HOURS = 24
    PERMA_BLOCK_AFTER = 10

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "rate_limit",
        collection_name: str = "list",
    ):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def before_request(self, request):
        client = request.scope.get("client") or ("unknown", 0)
        client_ip = client[0] or "unknown"
        now = datetime.utcnow()

        window_start_cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        perma_window_cutoff = now - timedelta(hours=self.PERMA_WINDOW_HOURS)

        key = client_ip
        doc = await self.collection.find_one({"_id": key})

        if doc and doc.get("permanent_blocked"):
            return {
                "status_code": 403,
                "body": f"Access permanently blocked for IP {client_ip}.",
                "headers": [],
            }

        if doc:
            blocked_until = doc.get("blocked_until")
            if isinstance(blocked_until, datetime) and now < blocked_until:
                retry_after = max(0, int((blocked_until - now).total_seconds()))
                return {
                    "status_code": 429,
                    "body": f"Too many requests from {client_ip}. Temporarily blocked.",
                    "headers": [("Retry-After", str(retry_after))],
                }

        if (
            not doc
            or doc.get("window_start") is None
            or doc["window_start"] < window_start_cutoff
        ):
            violations = doc.get("violations", 0) if doc else 0

            await self.collection.replace_one(
                {"_id": key},
                {
                    "_id": key,
                    "ip": client_ip,
                    "count": 1,
                    "window_start": now,
                    "violations": violations,
                    "blocked_until": None,
                    "permanent_blocked": doc.get("permanent_blocked", False) if doc else False,
                    "permanent_blocked_at": doc.get("permanent_blocked_at") if doc else None,
                    "violation_events": doc.get("violation_events", []) if doc else [],
                },
                upsert=True,
            )
            return None

        count = int(doc.get("count", 0))

        if count >= self.MAX_REQUESTS:
            violations = int(doc.get("violations", 0)) + 1

            await self.collection.update_one(
                {"_id": key},
                {
                    "$set": {"violations": violations},
                    "$push": {"violation_events": now},
                    "$pull": {"violation_events": {"$lt": perma_window_cutoff}},
                },
            )

            doc = await self.collection.find_one({"_id": key})
            events_last_24h = len((doc or {}).get("violation_events", []))

            update = {}

            if violations >= self.BLOCK_AFTER_VIOLATIONS:
                update["blocked_until"] = now + timedelta(seconds=self.BLOCK_FOR_SECONDS)

            if events_last_24h >= self.PERMA_BLOCK_AFTER:
                update["permanent_blocked"] = True
                update["permanent_blocked_at"] = now

            if update:
                await self.collection.update_one({"_id": key}, {"$set": update})

            return {
                "status_code": 429,
                "body": f"Rate limit exceeded for IP {client_ip}.",
                "headers": [],
            }

        await self.collection.update_one({"_id": key}, {"$inc": {"count": 1}})
        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        return None

