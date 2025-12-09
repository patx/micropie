from datetime import datetime, timedelta
from micropie import App, HttpMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError


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
    BLOCK_FOR_SECONDS = 900        # how long to temporarily block (seconds)

    PERMA_WINDOW_HOURS = 24        # lookback window for permanent block
    PERMA_BLOCK_AFTER = 10         # violations in window before permanent block

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "vegy_security",
        collection_name: str = "rate_limits_global",
    ):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def before_request(self, request):
        client = request.scope.get("client") or ("unknown", 0)
        client_ip = client[0]
        now = datetime.utcnow()

        window_start_cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        perma_window_cutoff = now - timedelta(hours=self.PERMA_WINDOW_HOURS)

        key = client_ip  # one document per IP

        try:
            doc = await self.collection.find_one({"_id": key})
        except PyMongoError:
            # If Mongo is unhappy, don't take the whole app down.
            return None

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
            permanent_blocked = doc.get("permanent_blocked", False) if doc else False
            first_violation_at = doc.get("first_violation_at") if doc else None
            violation_count_window = doc.get("violation_count_window", 0) if doc else 0

            try:
                await self.collection.replace_one(
                    {"_id": key},
                    {
                        "_id": key,
                        "ip": client_ip,
                        "count": 1,
                        "window_start": now,
                        "violations": violations,
                        "blocked_until": None,
                        "permanent_blocked": permanent_blocked,
                        "first_violation_at": first_violation_at,
                        "violation_count_window": violation_count_window,
                    },
                    upsert=True,
                )
            except PyMongoError:
                # Soft-fail if Mongo is down
                return None

            return None  # allow request

        # 3. Window active -> check count
        count = doc.get("count", 0)

        if count >= self.MAX_REQUESTS:
            # Exceeded this window
            violations = doc.get("violations", 0) + 1

            first_violation_at = doc.get("first_violation_at")
            violation_count_window = doc.get("violation_count_window", 0)

            # Reset 24h window if outside lookback
            if not first_violation_at or first_violation_at < perma_window_cutoff:
                first_violation_at = now
                violation_count_window = 1
            else:
                violation_count_window += 1

            update_fields = {
                "violations": violations,
                "first_violation_at": first_violation_at,
                "violation_count_window": violation_count_window,
            }

            # Temporary block if too many violations overall
            if violations >= self.BLOCK_AFTER_VIOLATIONS:
                update_fields["blocked_until"] = now + timedelta(
                    seconds=self.BLOCK_FOR_SECONDS
                )

            # Permanent block if too many violations in last 24 hours
            if violation_count_window >= self.PERMA_BLOCK_AFTER:
                update_fields["permanent_blocked"] = True
                update_fields["permanent_blocked_at"] = now

            try:
                await self.collection.update_one(
                    {"_id": key},
                    {"$set": update_fields},
                )
            except PyMongoError:
                # If the write fails, still return 429 so the attacker doesn't get through.
                return {
                    "status_code": 429,
                    "body": f"Rate limit exceeded for IP {client_ip}.",
                    "headers": [],
                }

            return {
                "status_code": 429,
                "body": f"Rate limit exceeded for IP {client_ip}.",
                "headers": [],
            }

        # 4. Still within limit -> increment count
        try:
            await self.collection.update_one(
                {"_id": key},
                {"$inc": {"count": 1}},
            )
        except PyMongoError:
            # Soft-fail on logging error
            return None

        return None  # allow request

    async def after_request(self, request, status_code, response_body, extra_headers):
        # No-op for now
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
