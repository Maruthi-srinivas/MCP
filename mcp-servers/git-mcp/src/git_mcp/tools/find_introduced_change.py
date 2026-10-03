"""Best-effort lookup of the commit that last changed one line."""

from git_mcp.git import commands
from git_mcp.logging import observed_tool


@observed_tool
def find_introduced_change(repository_id: str, path: str, line: int) -> dict:
    """Use git log -L for a single line. This does not search by symbol name."""
    return commands.introduced_change(repository_id, path, line)
