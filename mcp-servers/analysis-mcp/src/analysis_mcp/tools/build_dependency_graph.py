"""Import edges plus name-matched call edges."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.logging import observed_tool


@observed_tool
def build_dependency_graph(repository_id: str) -> dict:
    """Return nodes and edges. A call edge is inferred because it is a name match, not a runtime trace."""
    artifact = ensure_artifact(repository_id)
    return {
        "repository_id": repository_id,
        "nodes": artifact["nodes"],
        "edges": artifact["edges"],
        "truncated": artifact["truncated"],
    }
