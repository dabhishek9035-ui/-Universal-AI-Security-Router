"""Per-key token-bucket rate limiter (in-process; swap for Redis at scale)."""
from __future__ import annotations

import threading
import time

from fastapi import Header, HTTPException

_buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
_lock = threading.Lock()


def _take_token(key: str, rate_per_min: int) -> None:
    now = time.monotonic()
    capacity = float(rate_per_min)
    refill_rate = capacity / 60.0  # tokens per second
    with _lock:
        tokens, last = _buckets.get(key, (capacity, now))
        tokens = min(capacity, tokens + (now - last) * refill_rate)
        if tokens < 1.0:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        tokens -= 1.0
        _buckets[key] = (tokens, now)


async def rate_limit(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency. Auth (require_tenant) runs separately; unknown keys
    still consume a bucket so brute-forcing keys gets throttled too."""
    if not x_api_key:
        return  # missing header -> auth dependency returns 401
    _take_token(x_api_key, 120)
