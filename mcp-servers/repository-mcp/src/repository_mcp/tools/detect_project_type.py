"""Report languages and a few Python frameworks from files and imports."""

from repository_mcp.intelligence.index import ensure_index, require_python
from repository_mcp.intelligence.project_type import detect
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root


@observed_tool
def detect_project_type(repository_id: str) -> dict:
    """Detect Python and obvious frameworks such as FastAPI, Flask, and Django."""
    index = ensure_index(repository_id)
    require_python(index)
    detected = detect(index, repository_root(repository_id))
    return {
        "repository_id": repository_id,
        "languages": detected["languages"],
        "frameworks": detected["frameworks"],
        "warnings": index["warnings"],
        "truncated": bool(index.get("truncated")),
    }
