"""FastAPI, Flask, and Django routes found in the AST."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.logging import observed_tool


@observed_tool
def detect_api_endpoints(repository_id: str) -> dict:
    """Return HTTP routes. Each item has a framework, method, path, file, and line."""
    artifact = ensure_artifact(repository_id)
    return {"repository_id": repository_id, "endpoints": artifact["endpoints"], "truncated": artifact["truncated"]}
