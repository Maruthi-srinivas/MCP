"""Working tree status. This does not refresh remotes."""

from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_git_status(repository_id: str) -> dict:
    """Return HEAD, the branch name, and porcelain entries. A clean clone has no entries."""
    return commands.status(repository_id)
