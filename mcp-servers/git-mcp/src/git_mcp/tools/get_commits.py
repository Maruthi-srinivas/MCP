"""Paged commit history for one ref."""

from git_mcp.config import bounded_page
from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_commits(repository_id: str, ref: str = "HEAD", page: int = 1, page_size: int | None = None) -> dict:
    """Return SHA, author, date, and subject for one page of commits."""
    page, size = bounded_page(page, page_size)
    return commands.commits(repository_id, ref, page, size)
