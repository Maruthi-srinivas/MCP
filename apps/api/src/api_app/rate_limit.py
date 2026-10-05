"""Shared counters for import and analysis requests."""

import time

from api_app.cache import client


def allow(kind: str, limit: int) -> bool:
    """True when this minute is still under the limit. The key expires on its own."""
    bucket = int(time.time() // 60)
    key = f"rate:{kind}:{bucket}"
    store = client()
    count = store.incr(key)
    if count == 1:
        store.expire(key, 120)
    return count <= limit
