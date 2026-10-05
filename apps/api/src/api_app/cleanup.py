"""Delete old workspaces and keep the database row."""

import shutil
from pathlib import Path

from api_app.config import get_settings
from api_app import db


def expire_workspaces(ttl_seconds: int | None = None) -> list[str]:
    """Mark ready repositories older than the TTL as expired and remove their directories."""
    settings = get_settings()
    seconds = settings.workspace_ttl_seconds if ttl_seconds is None else ttl_seconds
    root = Path(settings.workspace_root).resolve()
    expired: list[str] = []
    for row in db.repositories_older_than(seconds):
        path = Path(row["workspace_path"]).resolve()
        if _inside(path, root) and path.exists():
            shutil.rmtree(path)
        db.mark_expired(row["repository_id"])
        expired.append(row["repository_id"])
    return expired


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
