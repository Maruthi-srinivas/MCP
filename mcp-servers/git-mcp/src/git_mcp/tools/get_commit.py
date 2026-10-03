"""Metadata for one commit."""

from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_commit(repository_id: str, ref: str) -> dict:
    """Return the SHA, author, date, and subject for a branch, tag, or full SHA."""
    return commands.commit(repository_id, ref)
