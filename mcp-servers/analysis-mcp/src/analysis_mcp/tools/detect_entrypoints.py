"""main.py, app.py, __main__ guards, and FastAPI or Flask assignments."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.logging import observed_tool


@observed_tool
def detect_entrypoints(repository_id: str) -> dict:
    """List likely process entrypoints with a path, line, and reason."""
    artifact = ensure_artifact(repository_id)
    return {"repository_id": repository_id, "entrypoints": artifact["entrypoints"], "truncated": artifact["truncated"]}
