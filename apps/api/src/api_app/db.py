"""PostgreSQL access. Each call opens its own connection."""

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from api_app.config import get_settings


def connect():
    return psycopg.connect(get_settings().database_url, row_factory=dict_row)


def ping() -> None:
    with connect() as connection:
        connection.execute("SELECT 1")


def applied_versions() -> set[str]:
    with connect() as connection:
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def mark_applied(version: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
            (version,),
        )
        connection.commit()


def execute_script(sql: str) -> None:
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    with connect() as connection:
        with connection.transaction():
            for statement in statements:
                connection.execute(statement)


def find_job_by_key(caller_id: str, idempotency_key: str) -> dict | None:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM jobs WHERE caller_id = %s AND idempotency_key = %s",
            (caller_id, idempotency_key),
        ).fetchone()


def insert_job(job: dict) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, kind, status, error_code, repository_id, idempotency_key, payload, caller_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job["id"],
                job["kind"],
                job["status"],
                job.get("error_code"),
                job.get("repository_id"),
                job.get("idempotency_key"),
                Jsonb(job.get("payload") or {}),
                job.get("caller_id"),
            ),
        )
        connection.commit()


def claim_job() -> dict | None:
    with connect() as connection:
        with connection.transaction():
            return connection.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = now()
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
                """
            ).fetchone()


def finish_job(job_id: str, status: str, error_code: str | None, payload: dict | None = None) -> None:
    with connect() as connection:
        if payload is None:
            connection.execute(
                """
                UPDATE jobs
                SET status = %s, error_code = %s, updated_at = now()
                WHERE id = %s
                """,
                (status, error_code, job_id),
            )
        else:
            connection.execute(
                """
                UPDATE jobs
                SET status = %s, error_code = %s, payload = %s, updated_at = now()
                WHERE id = %s
                """,
                (status, error_code, Jsonb(payload), job_id),
            )
        connection.commit()


def get_repository_row(repository_id: str) -> dict | None:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM repositories WHERE repository_id = %s",
            (repository_id,),
        ).fetchone()


def latest_job(repository_id: str, kind: str | None = None) -> dict | None:
    with connect() as connection:
        if kind:
            return connection.execute(
                """
                SELECT * FROM jobs
                WHERE repository_id = %s AND kind = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (repository_id, kind),
            ).fetchone()
        return connection.execute(
            """
            SELECT * FROM jobs
            WHERE repository_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (repository_id,),
        ).fetchone()


def remember_idempotency(repository_id: str, idempotency_key: str | None) -> None:
    if not idempotency_key:
        return
    with connect() as connection:
        connection.execute(
            """
            UPDATE repositories
            SET idempotency_key = %s
            WHERE repository_id = %s AND idempotency_key IS NULL
            """,
            (idempotency_key, repository_id),
        )
        connection.commit()


def replace_files(repository_id: str, rows: list[dict]) -> None:
    with connect() as connection:
        with connection.transaction():
            connection.execute("DELETE FROM repository_files WHERE repository_id = %s", (repository_id,))
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO repository_files (repository_id, path, size_bytes, language)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (repository_id, row["path"], row["size_bytes"], row["language"]),
                )


def replace_symbols(repository_id: str, rows: list[dict]) -> None:
    with connect() as connection:
        with connection.transaction():
            connection.execute("DELETE FROM symbols WHERE repository_id = %s", (repository_id,))
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO symbols (repository_id, name, kind, path, start_line, end_line)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        repository_id,
                        row["name"],
                        row["kind"],
                        row["path"],
                        row["start_line"],
                        row["end_line"],
                    ),
                )


def replace_dependencies(repository_id: str, rows: list[dict]) -> None:
    with connect() as connection:
        with connection.transaction():
            connection.execute("DELETE FROM dependencies WHERE repository_id = %s", (repository_id,))
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO dependencies (repository_id, name, version, source)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (repository_id, row["name"], row.get("version") or "", row.get("source") or ""),
                )


def insert_analysis(repository_id: str, commit_sha: str, analyzer_version: str, body: dict) -> str:
    import uuid

    run_id = str(uuid.uuid4())
    with connect() as connection:
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO analysis_runs (id, repository_id, commit_sha, analyzer_version, status)
                VALUES (%s, %s, %s, %s, 'succeeded')
                """,
                (run_id, repository_id, commit_sha, analyzer_version),
            )
            connection.execute(
                "INSERT INTO analysis_artifacts (run_id, body) VALUES (%s, %s)",
                (run_id, Jsonb(body)),
            )
    return run_id


def latest_architecture(repository_id: str) -> dict | None:
    with connect() as connection:
        return connection.execute(
            """
            SELECT runs.commit_sha, runs.analyzer_version, artifacts.body
            FROM analysis_runs AS runs
            JOIN analysis_artifacts AS artifacts ON artifacts.run_id = runs.id
            WHERE runs.repository_id = %s AND runs.status = 'succeeded'
            ORDER BY runs.created_at DESC
            LIMIT 1
            """,
            (repository_id,),
        ).fetchone()


def mark_expired(repository_id: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE repositories
            SET status = 'expired', updated_at = now()
            WHERE repository_id = %s
            """,
            (repository_id,),
        )
        connection.commit()


def repositories_older_than(seconds: int) -> list[dict]:
    with connect() as connection:
        return connection.execute(
            """
            SELECT repository_id, workspace_path
            FROM repositories
            WHERE status = 'ready'
              AND updated_at < now() - (%s * interval '1 second')
            """,
            (seconds,),
        ).fetchall()


def insert_session(session_id: str, repository_id: str, caller_id: str, messages: list[dict]) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO investigation_sessions (id, repository_id, caller_id, messages)
            VALUES (%s, %s, %s, %s)
            """,
            (session_id, repository_id, caller_id, Jsonb(messages)),
        )
        connection.commit()


def get_session(session_id: str) -> dict | None:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM investigation_sessions WHERE id = %s",
            (session_id,),
        ).fetchone()


def save_messages(session_id: str, messages: list[dict]) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE investigation_sessions SET messages = %s WHERE id = %s",
            (Jsonb(messages), session_id),
        )
        connection.commit()


def next_position(session_id: str) -> int:
    with connect() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(position), 0) AS position FROM tool_calls WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    return int(row["position"]) + 1


def insert_tool_calls(session_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    with connect() as connection:
        with connection.transaction():
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO tool_calls (
                        session_id, position, server, tool, status, duration_ms, arguments, argument_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        row["position"],
                        row.get("server") or "",
                        row["tool"],
                        row.get("status") or "",
                        int(row.get("duration_ms") or 0),
                        Jsonb(row.get("arguments") or {}),
                        row.get("argument_hash") or "",
                    ),
                )


def list_tool_calls(session_id: str) -> list[dict]:
    with connect() as connection:
        return connection.execute(
            """
            SELECT server, tool, status, duration_ms, arguments, argument_hash
            FROM tool_calls
            WHERE session_id = %s
            ORDER BY position
            """,
            (session_id,),
        ).fetchall()


def list_repositories(caller_id: str) -> list[dict]:
    with connect() as connection:
        return connection.execute(
            """
            SELECT repositories.repository_id, url, owner, name, ref, resolved_commit, status
            FROM repositories
            JOIN repository_access AS access
              ON access.repository_id = repositories.repository_id
            WHERE access.caller_id = %s
            ORDER BY repositories.updated_at DESC
            """,
            (caller_id,),
        ).fetchall()


def has_access(repository_id: str, caller_id: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1 FROM repository_access
            WHERE repository_id = %s AND caller_id = %s
            """,
            (repository_id, caller_id),
        ).fetchone()
    return row is not None


def grant_access(repository_id: str, caller_id: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO repository_access (repository_id, caller_id)
            VALUES (%s, %s)
            ON CONFLICT (repository_id, caller_id) DO NOTHING
            """,
            (repository_id, caller_id),
        )
        connection.commit()


def ensure_repository_stub(repository_id: str, url: str, owner: str, name: str, ref: str | None) -> None:
    """Create the row an access record can point at. Clone fills the commit and path."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, url, owner, name, ref, resolved_commit, workspace_path, status
            )
            VALUES (%s, %s, %s, %s, %s, '', '', 'importing')
            ON CONFLICT (repository_id) DO NOTHING
            """,
            (repository_id, url, owner, name, ref),
        )
        connection.commit()


def count_analysis_jobs(repository_id: str) -> int:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM jobs
            WHERE repository_id = %s AND kind = 'analyze'
            """,
            (repository_id,),
        ).fetchone()
    return int(row["count"])


def list_languages(repository_id: str) -> list[str]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT language
            FROM repository_files
            WHERE repository_id = %s
            ORDER BY language
            """,
            (repository_id,),
        ).fetchall()
    return [row["language"] for row in rows]


def list_dependencies(repository_id: str) -> list[dict]:
    with connect() as connection:
        return connection.execute(
            """
            SELECT name, version, source
            FROM dependencies
            WHERE repository_id = %s
            ORDER BY name, source
            """,
            (repository_id,),
        ).fetchall()


def list_jobs(repository_id: str) -> list[dict]:
    with connect() as connection:
        return connection.execute(
            """
            SELECT id, kind, status, error_code, created_at
            FROM jobs
            WHERE repository_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (repository_id,),
        ).fetchall()


def latest_session_job(session_id: str) -> dict | None:
    with connect() as connection:
        return connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE kind = 'investigate' AND payload->>'session_id' = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()


def list_proposals(session_id: str) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM proposals
            WHERE session_id = %s
            ORDER BY created_at
            """,
            (session_id,),
        ).fetchall()
    return [_proposal(row) for row in rows]


def get_proposal(proposal_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM proposals WHERE id = %s", (proposal_id,)).fetchone()
    return _proposal(row) if row else None


def claim_proposals(session_id: str, caller_id: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE proposals
            SET caller_id = %s, updated_at = now()
            WHERE session_id = %s AND caller_id IS NULL
            """,
            (caller_id, session_id),
        )
        connection.commit()


def approve_proposal(proposal_id: str, session_id: str, caller_id: str, approval_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            """
            UPDATE proposals
            SET status = 'approved',
                approval_id = %s,
                expires_at = now() + interval '10 minutes',
                caller_id = %s,
                updated_at = now()
            WHERE id = %s AND session_id = %s AND status = 'proposed'
            RETURNING *
            """,
            (approval_id, caller_id, proposal_id, session_id),
        ).fetchone()
        connection.commit()
    return _proposal(row) if row else None


def reject_proposal(proposal_id: str, session_id: str, caller_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            """
            UPDATE proposals
            SET status = 'rejected', caller_id = %s, updated_at = now()
            WHERE id = %s AND session_id = %s AND status = 'proposed'
            RETURNING *
            """,
            (caller_id, proposal_id, session_id),
        ).fetchone()
        connection.commit()
    return _proposal(row) if row else None


def expire_proposal(proposal_id: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE proposals
            SET status = 'expired', expires_at = now() - interval '1 minute', updated_at = now()
            WHERE id = %s
            """,
            (proposal_id,),
        )
        connection.commit()


def _proposal(row: dict | None) -> dict | None:
    if row is None:
        return None
    expires = row.get("expires_at")
    return {
        "proposal_id": str(row["id"]),
        "repository_id": row["repository_id"],
        "session_id": str(row["session_id"]) if row.get("session_id") else "",
        "caller_id": row.get("caller_id") or "",
        "base_commit": row.get("base_commit") or "",
        "diff": row["diff_text"],
        "diff_hash": row["diff_hash"],
        "status": row["status"],
        "approval_id": str(row["approval_id"]) if row.get("approval_id") else "",
        "expires_at": expires.isoformat() if expires else "",
        "files": _diff_files(row["diff_text"]),
    }


def _diff_files(diff: str) -> list[str]:
    paths = []
    for line in str(diff).splitlines():
        if not line.startswith("+++ "):
            continue
        path = line[4:].strip().split("\t", 1)[0]
        if path.startswith("b/") or path.startswith("a/"):
            path = path[2:]
        paths.append(path)
    return paths


def cleanup_job_pending() -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id FROM jobs
            WHERE kind = 'cleanup' AND status IN ('queued', 'running')
            LIMIT 1
            """
        ).fetchone()
    return row is not None
