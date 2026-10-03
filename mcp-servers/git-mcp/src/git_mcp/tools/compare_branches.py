"""Compare two branch tips without returning the full patch."""

from git_mcp.config import get_settings
from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def compare_branches(repository_id: str, base: str, head: str) -> dict:
    """Return both tip SHAs, ahead/behind counts, and a bounded list of changed paths."""
    return commands.compare(repository_id, base, head, get_settings().max_page_size)
