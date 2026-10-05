"""Read a stored proposal. This does not change the file."""

from investigator_shared.errors import ToolFailure

from workspace_mcp.logging import observed_tool
from workspace_mcp.patch import parse_diff
from workspace_mcp.store import get_proposal


@observed_tool
def preview_patch(proposal_id: str) -> dict:
    """Return the stored diff and its status."""
    row = get_proposal(proposal_id)
    if row is None:
        raise ToolFailure("PROPOSAL_NOT_FOUND", "Proposal was not found.", False)
    paths = [item["path"] for item in parse_diff(row["diff_text"])]
    return {
        "proposal_id": row["id"],
        "status": row["status"],
        "files": paths,
        "diff": row["diff_text"],
        "approval_id": row["approval_id"],
        "expires_at": row["expires_at"],
    }
