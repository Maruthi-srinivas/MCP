"""Redis cache and locks. MCP tool functions never call this module."""

import hashlib
import json
import logging

import redis

from api_app.config import get_settings

log = logging.getLogger("api")


def client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def ping() -> None:
    client().ping()


def tool_key(repository_id: str, commit_sha: str, tool: str, arguments: dict) -> str:
    digest = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"tool:{repository_id}:{commit_sha}:{tool}:{digest}"


def analysis_key(repository_id: str, commit_sha: str) -> str:
    return f"analysis:{repository_id}:{commit_sha}"


def lock_key(repository_id: str) -> str:
    return f"lock:analysis:{repository_id}"


def get_json(key: str) -> dict | None:
    raw = client().get(key)
    if not raw:
        return None
    return json.loads(raw)


def set_json(key: str, payload: dict) -> None:
    client().set(key, json.dumps(payload), ex=get_settings().cache_ttl_seconds)


def acquire(key: str, ttl_seconds: int = 120) -> bool:
    return bool(client().set(key, "1", nx=True, ex=ttl_seconds))


def release(key: str) -> None:
    client().delete(key)


def note_hit(tool: str, key: str) -> None:
    """Log the key prefix only. The value can contain repository text."""
    log.info("cache_hit tool=%s key=%s", tool, key.split(":")[0])
