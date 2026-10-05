"""Proposal rows. Postgres when DATABASE_URL is set, otherwise a JSON file."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from investigator_shared.errors import ToolFailure
from investigator_shared.registry import workspace_root

from workspace_mcp.config import get_settings

_lock = threading.Lock()


def insert_proposal(
    proposal_id: str,
    repository_id: str,
    session_id: str,
    base_commit: str,
    diff_text: str,
    diff_hash: str,
) -> None:
    row = {
        "id": proposal_id,
        "repository_id": repository_id,
        "session_id": session_id or "",
        "caller_id": "",
        "base_commit": base_commit,
        "diff_text": diff_text,
        "diff_hash": diff_hash,
        "status": "proposed",
        "approval_id": "",
        "expires_at": "",
    }
    if get_settings().database_url:
        _insert_sql(row)
        return
    with _lock:
        rows = _read_json()
        rows.append(row)
        _write_json(rows)


def get_proposal(proposal_id: str) -> dict | None:
    if get_settings().database_url:
        return _get_sql(proposal_id)
    with _lock:
        for row in _read_json():
            if row["id"] == proposal_id:
                return dict(row)
    return None


def save_proposal(row: dict) -> None:
    if get_settings().database_url:
        _save_sql(row)
        return
    with _lock:
        rows = _read_json()
        for index, existing in enumerate(rows):
            if existing["id"] == row["id"]:
                rows[index] = row
                _write_json(rows)
                return
    raise ToolFailure("PROPOSAL_NOT_FOUND", "Proposal was not found.", False)


def _json_path() -> Path:
    path = workspace_root() / "proposals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json() -> list[dict]:
    path = _json_path()
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(rows: list[dict]) -> None:
    _json_path().write_text(json.dumps(rows), encoding="utf-8")


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(get_settings().database_url, row_factory=dict_row)


def _insert_sql(row: dict) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO proposals (
                id, repository_id, session_id, caller_id, base_commit,
                diff_text, diff_hash, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'proposed')
            """,
            (
                row["id"],
                row["repository_id"],
                row["session_id"] or None,
                None,
                row["base_commit"],
                row["diff_text"],
                row["diff_hash"],
            ),
        )
        connection.commit()


def _get_sql(proposal_id: str) -> dict | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM proposals WHERE id = %s", (proposal_id,)).fetchone()
    return _public(row) if row else None


def _save_sql(row: dict) -> None:
    expires = row["expires_at"] or None
    with _connect() as connection:
        updated = connection.execute(
            """
            UPDATE proposals
            SET status = %s,
                approval_id = %s,
                expires_at = %s,
                session_id = COALESCE(session_id, %s),
                caller_id = COALESCE(caller_id, %s),
                updated_at = now()
            WHERE id = %s
            """,
            (
                row["status"],
                row["approval_id"] or None,
                expires,
                row.get("session_id") or None,
                row.get("caller_id") or None,
                row["id"],
            ),
        )
        connection.commit()
        if updated.rowcount != 1:
            raise ToolFailure("PROPOSAL_NOT_FOUND", "Proposal was not found.", False)


def _public(row: dict) -> dict:
    expires = row.get("expires_at")
    if isinstance(expires, datetime):
        expires = expires.astimezone(timezone.utc).isoformat()
    return {
        "id": str(row["id"]),
        "repository_id": row["repository_id"],
        "session_id": row.get("session_id") or "",
        "caller_id": row.get("caller_id") or "",
        "base_commit": row.get("base_commit") or "",
        "diff_text": row["diff_text"],
        "diff_hash": row["diff_hash"],
        "status": row["status"],
        "approval_id": str(row["approval_id"]) if row.get("approval_id") else "",
        "expires_at": expires or "",
    }
