"""List coarse services from packages and entrypoint modules."""

from repository_mcp.intelligence.index import ensure_index, require_python
from repository_mcp.intelligence.services import detect
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root


@observed_tool
def detect_services(repository_id: str) -> dict:
    """Return top-level Python packages and modules that look like process entrypoints."""
    index = ensure_index(repository_id)
    require_python(index)
    return {
        "repository_id": repository_id,
        "services": detect(index, repository_root(repository_id)),
        "warnings": index["warnings"],
        "truncated": bool(index.get("truncated")),
    }
