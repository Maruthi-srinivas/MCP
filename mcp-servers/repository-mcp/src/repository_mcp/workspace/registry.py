"""JSON registry on the workspace volume. One file, locked around each update."""

import fcntl
import json
from typing import Any

from investigator_shared.registry import get_repository as read_repository
from repository_mcp.config import get_settings


def registry_path():
    return get_settings().workspace_root / "registry.json"


def _read_unlocked(handle) -> dict[str, Any]:
    handle.seek(0)
    raw = handle.read()
    if not raw.strip():
        return {"repositories": {}}
    data = json.loads(raw)
    data.setdefault("repositories", {})
    return data


def save_repository(record: dict[str, Any]) -> None:
    """Insert or replace one repository record."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = _read_unlocked(handle)
            data["repositories"][record["repository_id"]] = record
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def get_repository(repository_id: str) -> dict[str, Any]:
    """Return the stored record or raise REPOSITORY_NOT_FOUND."""
    return read_repository(repository_id)
