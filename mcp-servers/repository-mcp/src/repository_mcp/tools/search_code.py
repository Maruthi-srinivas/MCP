"""Search file contents with ripgrep, skipping .git and oversized files."""

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.logging import observed_tool
from repository_mcp.search.ripgrep import search_workspace
from repository_mcp.workspace.paths import repository_root


@observed_tool
def search_code(repository_id: str, query: str, file_pattern: str | None = None) -> dict:
    """Find a text query and return file, line, and a short snippet for each hit."""
    if not query or not query.strip():
        raise ToolFailure("INTERNAL_ERROR", "query must not be empty.", False)
    if file_pattern is not None and (file_pattern.startswith("/") or ".." in file_pattern):
        raise ToolFailure("INVALID_PATH", "file_pattern must be a relative glob.", False)

    root = repository_root(repository_id)
    matches, truncated = search_workspace(root, query, file_pattern, get_settings())
    return {
        "repository_id": repository_id,
        "query": query,
        "matches": matches,
        "truncated": truncated,
    }
