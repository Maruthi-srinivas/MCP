"""Commits that changed one file. The patch is a separate get_diff call."""

from git_mcp.config import bounded_page
from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_file_history(
    repository_id: str,
    path: str,
    ref: str = "HEAD",
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    """List commits that touched path. Each item has a SHA, author, date, and subject."""
    page, size = bounded_page(page, page_size)
    return commands.file_history(repository_id, path, ref, page, size)
