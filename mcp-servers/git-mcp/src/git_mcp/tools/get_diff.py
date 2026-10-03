"""Bounded diff between two refs."""

from git_mcp.config import get_settings
from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_diff(repository_id: str, base: str, head: str) -> dict:
    """Diff base and head. The result includes both resolved SHAs and cuts long patches."""
    return commands.diff(repository_id, base, head, get_settings().max_diff_lines)
