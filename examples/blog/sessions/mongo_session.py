import time
from typing import Any, Dict, Optional

from mongokv import Mkv
from micropie import SessionBackend


class MkvSessionBackend(SessionBackend):
    """
    Session backend backed by mongokv.Mkv.

    Storage schema (per session_id):
        key = session_id
        value = {
            "data": { ...session dict... },
            "expires_at": <unix_epoch_seconds>
        }

    Notes:
    - Expiration is enforced on load (lazy cleanup).
    - save(..., {}, 0) deletes (matches MicroPie logout behavior).
    """

    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        collection_name: str = "sessions",
        *,
        key_prefix: str = "sess:",
    ) -> None:
        self.store = Mkv(mongo_uri, db_name, collection_name)
        self.key_prefix = key_prefix

    def _k(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"

    async def load(self, session_id: str) -> Dict[str, Any]:
        if not session_id:
            return {}

        key = self._k(session_id)

        try:
            payload = await self.store.get(key)
        except KeyError:
            return {}
        except Exception:
            # If you prefer, log this instead of swallowing.
            return {}

        if not isinstance(payload, dict):
            # Corrupt/unexpected; treat as empty and delete
            try:
                await self.store.remove(key)
            except Exception:
                pass
            return {}

        expires_at = payload.get("expires_at")
        if isinstance(expires_at, (int, float)) and time.time() > float(expires_at):
            # Expired: delete and return empty
            try:
                await self.store.remove(key)
            except Exception:
                pass
            return {}

        data = payload.get("data", {})
        return data if isinstance(data, dict) else {}

    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        if not session_id:
            return

        key = self._k(session_id)

        # MicroPie uses save(session_id, {}, 0) for logout/delete
        if not data or timeout <= 0:
            try:
                await self.store.remove(key)
            except Exception:
                pass
            return

        expires_at = time.time() + int(timeout)

        payload = {
            "data": data,
            "expires_at": expires_at,
        }

        await self.store.set(key, payload)

