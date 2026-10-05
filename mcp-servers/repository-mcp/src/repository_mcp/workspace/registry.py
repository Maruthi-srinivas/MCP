"""Persist one repository record.

PostgreSQL is used when DATABASE_URL is set. Tests that leave it unset keep
the JSON file on the workspace volume.
"""

import fcntl
import json
import os
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
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        _save_postgres(record, database_url)
        return
    _save_json(record)


def _save_postgres(record: dict[str, Any], database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, url, owner, name, ref, resolved_commit, workspace_path, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (repository_id) DO UPDATE SET
                url = EXCLUDED.url,
                owner = EXCLUDED.owner,
                name = EXCLUDED.name,
                ref = EXCLUDED.ref,
                resolved_commit = EXCLUDED.resolved_commit,
                workspace_path = EXCLUDED.workspace_path,
                status = EXCLUDED.status,
                updated_at = now()
            """,
            (
                record["repository_id"],
                record["url"],
                record["owner"],
                record["name"],
                record.get("ref"),
                record["resolved_commit"],
                record["workspace_path"],
                record["status"],
            ),
        )
        connection.commit()


def _save_json(record: dict[str, Any]) -> None:
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
