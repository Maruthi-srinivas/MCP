"""List local and remote-tracking branches that are already in the clone."""

from git_mcp.config import get_settings
from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def get_branches(repository_id: str) -> dict:
    """Return branch names and tip SHAs. This does not fetch from the network."""
    return commands.branches(repository_id, get_settings().max_branches)
