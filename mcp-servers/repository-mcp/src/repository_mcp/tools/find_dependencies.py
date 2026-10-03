"""List dependencies declared in requirements files and pyproject.toml."""

from repository_mcp.intelligence.dependencies import find_manifest_dependencies
from repository_mcp.intelligence.index import ensure_index, require_python
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root


@observed_tool
def find_dependencies(repository_id: str) -> dict:
    """Return name, version, and source file. A missing manifest is an empty list."""
    index = ensure_index(repository_id)
    require_python(index)
    dependencies, warnings = find_manifest_dependencies(repository_root(repository_id))
    return {
        "repository_id": repository_id,
        "dependencies": dependencies,
        "warnings": index["warnings"] + warnings,
        "truncated": bool(index.get("truncated")),
    }
