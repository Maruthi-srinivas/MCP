"""Return the stored metadata for one imported repository."""

from repository_mcp.logging import observed_tool
from repository_mcp.workspace.ids import require_repository_id
from repository_mcp.workspace.registry import get_repository


@observed_tool
def get_repository_info(repository_id: str) -> dict:
    """Read owner, name, requested ref, and the commit SHA last fetched."""
    require_repository_id(repository_id)
    record = get_repository(repository_id)
    return {
        "repository_id": record["repository_id"],
        "url": record["url"],
        "owner": record["owner"],
        "name": record["name"],
        "ref": record["ref"],
        "resolved_commit": record["resolved_commit"],
        "workspace_path": record["workspace_path"],
        "status": record["status"],
    }
