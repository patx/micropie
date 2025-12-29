from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta
from typing import Set

from pymongo import AsyncMongoClient, ReturnDocument
from micropie import HttpMiddleware


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except Exception:
        return None


class MongoRateLimitMiddleware(HttpMiddleware):
    """
    Global MongoDB-based rate limiter (Heroku + Cloudflare safe).

    - One document per client IP
    - Fixed window counter
    - Escalating temporary blocks
    - Permanent block based on 24h violation history
    - Fully atomic (single DB op per request)
    - PyMongo Async API (no Motor)

    Requires:
    - MongoDB 4.2+ (aggregation pipeline updates)
    """

    # --- rate config ---
    MAX_REQUESTS = 50
    WINDOW_SECONDS = 60

    BLOCK_AFTER_VIOLATIONS = 3
    BLOCK_FOR_SECONDS = 900

    PERMA_WINDOW_HOURS = 24
    PERMA_BLOCK_AFTER = 10

    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        collection_name: str = "rate_limits_global",
        *,
        allowed_hosts: Set[str] | None = None,
        trust_proxy_headers: bool = True,
        require_cf_ray: bool = True,
    ):
        self.client = AsyncMongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        # Security / proxy config
        self.allowed_hosts = allowed_hosts or set()
        self.trust_proxy_headers = trust_proxy_headers
        self.require_cf_ray = require_cf_ray

    # ---------------------------------------------------------
    # Real client IP resolution (for Cloudflare + Heroku or similar setups)
    # ---------------------------------------------------------

    def _client_ip(self, request) -> str:
        headers = getattr(request, "headers", {}) or {}

        # 1) Optional host allow-list (prevents origin bypass)
        if self.allowed_hosts:
            host = (headers.get("host") or "").split(":", 1)[0].lower()
            if host and host not in self.allowed_hosts:
                return "unknown"

        # 2) Only trust proxy headers if allowed
        can_trust = self.trust_proxy_headers
        if can_trust and self.require_cf_ray:
            can_trust = bool(headers.get("cf-ray"))

        if can_trust:
            # Cloudflare headers (best)
            for h in ("cf-connecting-ip", "true-client-ip"):
                ip = _valid_ip(headers.get(h))
                if ip:
                    return ip

            # Standard proxy chain
            xff = headers.get("x-forwarded-for")
            if isinstance(xff, str):
                ip = _valid_ip(xff.split(",", 1)[0])
                if ip:
                    return ip

            # Fallback proxy header
            ip = _valid_ip(headers.get("x-real-ip"))
            if ip:
                return ip

        # 3) ASGI scope fallback (Heroku router)
        client = request.scope.get("client") or ("unknown", 0)
        return _valid_ip(client[0]) or "unknown"

    # ---------------------------------------------------------
    # Middleware hook
    # ---------------------------------------------------------

    async def before_request(self, request):
        client_ip = self._client_ip(request)
        now = datetime.utcnow()

        window_start_cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        perma_window_cutoff = now - timedelta(hours=self.PERMA_WINDOW_HOURS)

        key = client_ip

        doc = await self.collection.find_one_and_update(
            {"_id": key},
            [
                # 1) Baseline fields
                {
                    "$set": {
                        "_id": key,
                        "ip": client_ip,
                        "count": {"$ifNull": ["$count", 0]},
                        "window_start": {"$ifNull": ["$window_start", now]},
                        "violations": {"$ifNull": ["$violations", 0]},
                        "blocked_until": {"$ifNull": ["$blocked_until", None]},
                        "permanent_blocked": {"$ifNull": ["$permanent_blocked", False]},
                        "permanent_blocked_at": {"$ifNull": ["$permanent_blocked_at", None]},
                        "violation_events": {"$ifNull": ["$violation_events", []]},
                    }
                },

                # 2) Prune old violation events
                {
                    "$set": {
                        "violation_events": {
                            "$filter": {
                                "input": "$violation_events",
                                "as": "t",
                                "cond": {"$gte": ["$$t", perma_window_cutoff]},
                            }
                        }
                    }
                },

                # 3) Are we currently blocked?
                {
                    "$set": {
                        "_blocked_now": {
                            "$or": [
                                "$permanent_blocked",
                                {
                                    "$and": [
                                        {"$ne": ["$blocked_until", None]},
                                        {"$gt": ["$blocked_until", now]},
                                    ]
                                },
                            ]
                        }
                    }
                },

                # 4) Update window/count atomically (only if not blocked)
                {
                    "$set": {
                        "_window_expired": {
                            "$cond": [
                                "$_blocked_now",
                                False,
                                {"$lt": ["$window_start", window_start_cutoff]},
                            ]
                        }
                    }
                },
                {
                    "$set": {
                        "window_start": {
                            "$cond": [
                                "$_blocked_now",
                                "$window_start",
                                {"$cond": ["$_window_expired", now, "$window_start"]},
                            ]
                        },
                        "count": {
                            "$cond": [
                                "$_blocked_now",
                                "$count",
                                {"$cond": ["$_window_expired", 1, {"$add": ["$count", 1]}]},
                            ]
                        },
                    }
                },

                # 5) Over limit?
                {
                    "$set": {
                        "_over_limit": {
                            "$and": [
                                {"$not": "$_blocked_now"},
                                {"$gt": ["$count", self.MAX_REQUESTS]},
                            ]
                        }
                    }
                },

                # 6) Record violation if over limit
                {
                    "$set": {
                        "violations": {
                            "$cond": ["$_over_limit", {"$add": ["$violations", 1]}, "$violations"]
                        },
                        "violation_events": {
                            "$cond": [
                                "$_over_limit",
                                {"$concatArrays": ["$violation_events", [now]]},
                                "$violation_events",
                            ]
                        },
                    }
                },

                # 7) Temporary block escalation
                {
                    "$set": {
                        "blocked_until": {
                            "$cond": [
                                {
                                    "$and": [
                                        "$_over_limit",
                                        {"$gte": ["$violations", self.BLOCK_AFTER_VIOLATIONS]},
                                    ]
                                },
                                now + timedelta(seconds=self.BLOCK_FOR_SECONDS),
                                "$blocked_until",
                            ]
                        }
                    }
                },

                # 8) Permanent block escalation
                {"$set": {"_events_24h": {"$size": "$violation_events"}}},
                {
                    "$set": {
                        "permanent_blocked": {
                            "$cond": [
                                {
                                    "$and": [
                                        "$_over_limit",
                                        {"$gte": ["$_events_24h", self.PERMA_BLOCK_AFTER]},
                                    ]
                                },
                                True,
                                "$permanent_blocked",
                            ]
                        },
                        "permanent_blocked_at": {
                            "$cond": [
                                {
                                    "$and": [
                                        "$_over_limit",
                                        {"$gte": ["$_events_24h", self.PERMA_BLOCK_AFTER]},
                                        {"$eq": ["$permanent_blocked_at", None]},
                                    ]
                                },
                                now,
                                "$permanent_blocked_at",
                            ]
                        },
                    }
                },

                # 9) Cleanup temp fields
                {"$unset": ["_blocked_now", "_window_expired", "_over_limit", "_events_24h"]},
            ],
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"count": 1, "blocked_until": 1, "permanent_blocked": 1},
        )

        doc = doc or {}

        # --- responses ---
        if doc.get("permanent_blocked"):
            return {
                "status_code": 403,
                "body": f"Access permanently blocked for IP {client_ip}.",
                "headers": [],
            }

        blocked_until = doc.get("blocked_until")
        if isinstance(blocked_until, datetime) and now < blocked_until:
            retry_after = max(0, int((blocked_until - now).total_seconds()))
            return {
                "status_code": 429,
                "body": f"Too many requests from {client_ip}. Temporarily blocked.",
                "headers": [("Retry-After", str(retry_after))],
            }

        if int(doc.get("count", 0)) > self.MAX_REQUESTS:
            return {
                "status_code": 429,
                "body": f"Rate limit exceeded for IP {client_ip}.",
                "headers": [],
            }

        return None

    async def after_request(self, request, status_code, response_body, extra_headers):
        return None

