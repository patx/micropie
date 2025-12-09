from datetime import datetime, timedelta
from micropie import App, HttpMiddleware
from motor.motor_asyncio import AsyncIOMotorClient


class MongoRateLimitMiddleware(HttpMiddleware):
    """
    Global MongoDB-based rate limiter.

    - Same limit for all endpoints.
    - One doc per client IP.
    - Sliding time window + escalating temp block.
    - Permanent block if too many violations in a 24h period.
    """

    MAX_REQUESTS = 50              # allowed per window
    WINDOW_SECONDS = 60            # window length in seconds

    BLOCK_AFTER_VIOLATIONS = 3     # how many windows exceeded before temp block
    BLOCK_FOR_SECONDS = 900       # how long to temporarily block in seconds

    PERMA_WINDOW_HOURS = 24        # lookback window for permanent block
    PERMA_BLOCK_AFTER = 10         # violations in window before permanent block

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "vegy_security",
        collection_name: str = "rate_limits_global",
    ):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def before_request(self, request):
        client = request.scope.get("client") or ("unknown", 0)
        client_ip = client[0]
        now = datetime.utcnow()

        window_start_cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        perma_window_cutoff = now - timedelta(hours=self.PERMA_WINDOW_HOURS)

        key = client_ip  # one document per IP

        doc = await self.collection.find_one({"_id": key})

        # 0. Permanent block check
        if doc and doc.get("permanent_blocked"):
            return {
                "status_code": 403,
                "body": f"Access permanently blocked for IP {client_ip}.",
                "headers": [],
            }

        # 1. Temporary block check
        if doc:
            blocked_until = doc.get("blocked_until")
            if (
                blocked_until
                and isinstance(blocked_until, datetime)
                and now < blocked_until
            ):
                return {
                    "status_code": 429,
                    "body": f"Too many requests from {client_ip}. Temporarily blocked.",
                    "headers": [],
                }

        # 2. New window if no doc or window expired
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
                    # keep a small history of violation events
                    "violation_events": doc.get("violation_events", []) if doc else [],
                },
                upsert=True,
            )
            return None  # allow request

        # 3. Window active -> check count
        count = doc.get("count", 0)

        if count >= self.MAX_REQUESTS:
            # Exceeded this window
            violations = doc.get("violations", 0) + 1

            # Update violations + violation_events (pull old, push new)
            await self.collection.update_one(
                {"_id": key},
                {
                    "$set": {
                        "violations": violations,
                    },
                    "$push": {"violation_events": now},
                    "$pull": {"violation_events": {"$lt": perma_window_cutoff}},
                },
            )

            # Re-fetch to inspect updated violation_events
            doc = await self.collection.find_one({"_id": key})
            events = doc.get("violation_events", [])
            events_last_24h = len(events)

            update = {}

            # Escalate to temporary block if too many violations overall
            if violations >= self.BLOCK_AFTER_VIOLATIONS:
                blocked_until = now + timedelta(seconds=self.BLOCK_FOR_SECONDS)
                update["blocked_until"] = blocked_until

            # Permanent block if too many violations in last 24 hours
            if events_last_24h >= self.PERMA_BLOCK_AFTER:
                update["permanent_blocked"] = True
                update["permanent_blocked_at"] = now

            if update:
                await self.collection.update_one(
                    {"_id": key},
                    {"$set": update},
                )

            return {
                "status_code": 429,
                "body": f"Rate limit exceeded for IP {client_ip}.",
                "headers": [],
            }

        # 4. Still within limit -> increment count
        await self.collection.update_one(
            {"_id": key},
            {"$inc": {"count": 1}},
        )

        return None  # allow request

    async def after_request(self, request, status_code, response_body, extra_headers):
        pass


class MyApp(App):

    async def index(self):
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        return f"You have visited {self.request.session['visits']} times."


app = MyApp()
app.middlewares.append(
    MongoRateLimitMiddleware(
        mongo_uri="your uri here",
        db_name="example_db",
        collection_name="rate_limits_global",
    )
)
