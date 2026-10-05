"""Concurrent import slots. A TTL releases the slot if the job process stops."""

from api_app.cache import client
from api_app.config import get_settings

_TTL_SECONDS = 300


def acquire_import(caller_id: str) -> bool:
    """True when this caller is still under the concurrent import limit."""
    key = f"imports:active:{caller_id}"
    store = client()
    count = int(store.incr(key))
    store.expire(key, _TTL_SECONDS)
    if count <= get_settings().max_concurrent_imports:
        return True
    _floor(store, key)
    return False


def release_import(caller_id: str) -> None:
    """Return one slot. The count does not go below zero."""
    key = f"imports:active:{caller_id}"
    store = client()
    _floor(store, key)


def _floor(store, key: str) -> None:
    value = int(store.decr(key))
    if value < 0:
        store.set(key, 0, ex=_TTL_SECONDS)
