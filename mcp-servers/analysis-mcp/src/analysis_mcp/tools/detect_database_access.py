"""Imports and call sites that look like database access."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.logging import observed_tool


@observed_tool
def detect_database_access(repository_id: str) -> dict:
    """Return hints with file and line. A hint is not proof that a query ran."""
    artifact = ensure_artifact(repository_id)
    return {"repository_id": repository_id, "hints": artifact["database_hints"], "truncated": artifact["truncated"]}
