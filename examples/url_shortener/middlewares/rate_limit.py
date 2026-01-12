from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta
from typing import Set, Iterable

from pymongo import AsyncMongoClient, ReturnDocument
from micropie import HttpMiddleware


# ---------------------------------------------------------------------------
# IP helpers
# ---------------------------------------------------------------------------


def _valid_ip(value: str | None) -> str | None:
    """Parse and normalize an IP string, returning canonical string form or None."""
    try:
        if not value:
            return None
        return str(ipaddress.ip_address(value.strip()))
    except Exception:
        return None


# Cloudflare IPv4 + IPv6 ranges
# Source: https://www.cloudflare.com/ips/
_CLOUDFLARE_IP_RANGES: list[str] = [
    # IPv4
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    # IPv6
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]

_CLOUDFLARE_NETWORKS = [ipaddress.ip_network(n) for n in _CLOUDFLARE_IP_RANGES]


def _is_cloudflare_socket_ip(socket_ip: str | None) -> bool:
    """
    Returns True if the connecting socket IP belongs to Cloudflare's published ranges.
    This is the key anti-spoof check before trusting CF/XFF headers.
    """
    try:
        if not socket_ip:
            return False
        addr = ipaddress.ip_address(socket_ip)
        return any(addr in net for net in _CLOUDFLARE_NETWORKS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class MongoRateLimitMiddleware(HttpMiddleware):
    """
    Global MongoDB-based rate limiter with Cloudflare anti-spoofing.

    - One document per client key (IP, optionally IP+route bucket)
    - Fixed window counter
    - Escalating temporary blocks
    - Permanent block based on 24h violation history
    - Fully atomic (single DB op per request)
    - PyMongo Async API (no Motor)

    Security:
    - Only trusts CF/XFF headers if:
        1) trust_proxy_headers=True
        2) (optionally) CF-Ray is present when require_cf_ray=True
        3) the connecting socket IP (ASGI scope['client'][0]) is in Cloudflare IP ranges
      Otherwise, proxy headers are ignored.

    Notes:
    - Host allow-list is a sanity check, NOT sufficient to prevent origin bypass if the
      origin is publicly reachable.
    - Best defense: make origin only reachable from Cloudflare (Tunnel/firewall).
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
        # Optional: include METHOD+PATH in key (lets you set different limits by route)
        bucket_by_route: bool = False,
        # If we can't reliably identify the client, return 403 (recommended)
        fail_closed: bool = True,
    ):
        self.client = AsyncMongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        self.allowed_hosts = set(h.lower() for h in (allowed_hosts or set()))
        self.trust_proxy_headers = trust_proxy_headers
        self.require_cf_ray = require_cf_ray

        self.bucket_by_route = bucket_by_route
        self.fail_closed = fail_closed

    # ---------------------------------------------------------
    # Client identification
    # ---------------------------------------------------------

    def _host_allowed(self, headers: dict) -> bool:
        if not self.allowed_hosts:
            return True
        host = (headers.get("host") or "").split(":", 1)[0].lower()
        return bool(host) and host in self.allowed_hosts

    def _socket_ip(self, request) -> str | None:
        client = (request.scope or {}).get("client") or (None, 0)
        return _valid_ip(client[0])

    def _can_trust_proxy_headers(self, headers: dict, socket_ip: str | None) -> bool:
        if not self.trust_proxy_headers:
            return False
        if self.require_cf_ray and not headers.get("cf-ray"):
            return False
        # Critical anti-spoof: only trust if the peer socket IP is Cloudflare
        return _is_cloudflare_socket_ip(socket_ip)

    def _client_ip(self, request) -> str | None:
        headers = getattr(request, "headers", {}) or {}

        # Optional host sanity check
        if not self._host_allowed(headers):
            return None

        socket_ip = self._socket_ip(request)
        can_trust = self._can_trust_proxy_headers(headers, socket_ip)

        if can_trust:
            # Cloudflare headers (preferred)
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

        # Untrusted path: fall back to socket peer IP (Heroku router, etc.)
        return socket_ip

    def _key(self, client_ip: str, request) -> str:
        if not self.bucket_by_route:
            return client_ip
        method = (
            getattr(request, "method", None)
            or (request.scope or {}).get("method")
            or "GET"
        ).upper()
        path = (request.scope or {}).get("path") or "/"
        return f"{client_ip}|{method}|{path}"

    # ---------------------------------------------------------
    # Middleware hook
    # ---------------------------------------------------------

    async def before_request(self, request):
        client_ip = self._client_ip(request)

        # Avoid collapsing unknowns into a shared key (DoS vector)
        if not client_ip:
            if self.fail_closed:
                return {"status_code": 403, "body": "Forbidden.", "headers": []}
            return None  # fail open (not recommended)

        now = datetime.utcnow()

        window_start_cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        perma_window_cutoff = now - timedelta(hours=self.PERMA_WINDOW_HOURS)

        key = self._key(client_ip, request)

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
                        "permanent_blocked_at": {
                            "$ifNull": ["$permanent_blocked_at", None]
                        },
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
                # 4) Update window/count (only if not blocked)
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
                                {
                                    "$cond": [
                                        "$_window_expired",
                                        1,
                                        {"$add": ["$count", 1]},
                                    ]
                                },
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
                            "$cond": [
                                "$_over_limit",
                                {"$add": ["$violations", 1]},
                                "$violations",
                            ]
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
                                        {
                                            "$gte": [
                                                "$violations",
                                                self.BLOCK_AFTER_VIOLATIONS,
                                            ]
                                        },
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
                                        {
                                            "$gte": [
                                                "$_events_24h",
                                                self.PERMA_BLOCK_AFTER,
                                            ]
                                        },
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
                                        {
                                            "$gte": [
                                                "$_events_24h",
                                                self.PERMA_BLOCK_AFTER,
                                            ]
                                        },
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
                {
                    "$unset": [
                        "_blocked_now",
                        "_window_expired",
                        "_over_limit",
                        "_events_24h",
                    ]
                },
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
