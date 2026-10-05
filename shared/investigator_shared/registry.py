"""Lookup of one repository record.

Writes stay in Repository MCP. When DATABASE_URL is set, the row lives in
PostgreSQL. Otherwise the record stays in registry.json on the workspace volume.
"""

import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any

from investigator_shared.errors import ToolFailure

_REPO_ID = re.compile(r"^repo_[0-9a-f]{16}$")


def workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", "/workspaces"))


def registry_path() -> Path:
    return workspace_root() / "registry.json"


def require_repository_id(repository_id: str) -> str:
    if not _REPO_ID.match(repository_id):
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return repository_id


def get_repository(repository_id: str) -> dict[str, Any]:
    """Return the stored record or raise REPOSITORY_NOT_FOUND."""
    require_repository_id(repository_id)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return _repository_from_postgres(repository_id, database_url)
    return _repository_from_file(repository_id)


def _repository_from_postgres(repository_id: str, database_url: str) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT repository_id, url, owner, name, ref, resolved_commit, workspace_path, status
            FROM repositories
            WHERE repository_id = %s
            """,
            (repository_id,),
        ).fetchone()
    if row is None:
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return dict(row)


def _repository_from_file(repository_id: str) -> dict[str, Any]:
    path = registry_path()
    if not path.exists():
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            handle.seek(0)
            raw = handle.read()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    if not raw.strip():
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    data = json.loads(raw)
    record = data.get("repositories", {}).get(repository_id)
    if record is None:
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return record
