"""Paged class list."""

from analysis_mcp.analysis.artifact import ensure_artifact, page_items
from analysis_mcp.config import bounded_page
from analysis_mcp.logging import observed_tool


@observed_tool
def find_classes(repository_id: str, name: str = "", page: int = 1, page_size: int | None = None) -> dict:
    """List classes. An empty name returns a page. No match is an empty list."""
    page, size = bounded_page(page, page_size)
    artifact = ensure_artifact(repository_id)
    items = artifact["classes"]
    if name:
        items = [item for item in items if item["name"] == name]
    chosen, truncated = page_items(items, page, size)
    return {
        "repository_id": repository_id,
        "name": name,
        "page": page,
        "page_size": size,
        "classes": chosen,
        "truncated": truncated,
    }
