"""Per-user daily message quota — the hard spend ceiling on paid LLM calls.

A small JSON counter per user under ``DATA_DIR/quotas/`` reusing the conversation store's
atomic-write + async-lock primitives, so it inherits the same durability and single-worker
serialisation. The per-minute slowapi limiter resets on redeploy (in-memory); THIS counter
is disk-backed and is the real cap on how much a single user can spend in a day.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .config import DATA_DIR, QUOTA_DAILY_MESSAGES
from .storage_backend import (
    KeyedLocks,
    StorageCorruptionError,
    _atomic_write_json,
    _is_safe_id,
    _read_json_or_quarantine,
)

_KST = timezone(timedelta(hours=9))


class DailyQuota:
    def __init__(self, data_dir: str = DATA_DIR, limit: int = QUOTA_DAILY_MESSAGES):
        self.base = Path(data_dir) / "quotas"
        self.limit = limit
        self._lock_for = KeyedLocks()

    def _path(self, user_id: str) -> Path:
        if not _is_safe_id(user_id):
            raise ValueError("invalid user_id")
        return self.base / f"{user_id}.json"

    @staticmethod
    def _today(now: Optional[datetime] = None) -> str:
        return (now or datetime.now(_KST)).strftime("%Y-%m-%d")

    async def check_and_increment(self, user_id: str) -> bool:
        """Reserve one message for today. Returns True if allowed, False if over the limit.

        Resets automatically when the KST date rolls over. The increment is persisted only
        when allowed, so a rejected request does not consume quota.
        """
        async with self._lock_for(user_id):
            path = self._path(user_id)
            today = self._today()
            count = 0
            if path.exists():
                try:
                    data = _read_json_or_quarantine(path)
                    if isinstance(data, dict) and data.get("date") == today:
                        count = int(data.get("count", 0))
                except (StorageCorruptionError, ValueError, TypeError):
                    count = 0
            if count >= self.limit:
                return False
            await asyncio.to_thread(_atomic_write_json, path, {"date": today, "count": count + 1})
            return True


quota = DailyQuota()
