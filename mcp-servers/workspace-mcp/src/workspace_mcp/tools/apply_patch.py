"""Write an approved diff. Unapproved, expired, and repeated applies fail."""

import hashlib
from datetime import datetime, timezone

from investigator_shared.errors import ToolFailure
from investigator_shared.paths import repository_root

from workspace_mcp.checks import check_path
from workspace_mcp.config import get_settings
from workspace_mcp.logging import observed_tool
from workspace_mcp.patch import apply_to_text, parse_diff
from workspace_mcp.store import get_proposal, save_proposal


@observed_tool
def apply_patch(proposal_id: str, approval_id: str) -> dict:
    """Write the diff only when the approval row is still valid."""
    row = get_proposal(proposal_id)
    if row is None:
        raise ToolFailure("PROPOSAL_NOT_FOUND", "Proposal was not found.", False)
    if row["status"] == "applied":
        raise ToolFailure("ALREADY_APPLIED", "This proposal was already applied.", False)
    if row["status"] == "expired" or _expired(row):
        row["status"] = "expired"
        save_proposal(row)
        raise ToolFailure("APPROVAL_EXPIRED", "The approval has expired.", False)
    if row["status"] != "approved" or not approval_id or approval_id != row["approval_id"]:
        raise ToolFailure("APPROVAL_REQUIRED", "An owner approval is required.", False)
    digest = hashlib.sha256(row["diff_text"].encode("utf-8")).hexdigest()
    if digest != row["diff_hash"]:
        raise ToolFailure("PATCH_REJECTED", "Stored diff hash does not match.", False)
    settings = get_settings()
    root = repository_root(row["repository_id"])
    files = parse_diff(row["diff_text"])
    planned = []
    for item in files:
        target = check_path(root, item["path"], settings.path_prefix)
        if not target.is_file():
            raise ToolFailure("FILE_NOT_FOUND", "Patch target does not exist.", False)
        original = target.read_text(encoding="utf-8")
        planned.append((target, apply_to_text(original, item["hunks"])))
    for target, text in planned:
        target.write_text(text, encoding="utf-8")
    row["status"] = "applied"
    save_proposal(row)
    return {"proposal_id": proposal_id, "status": "applied", "files": [item["path"] for item in files]}


def _expired(row: dict) -> bool:
    raw = row.get("expires_at") or ""
    if not raw or row["status"] != "approved":
        return False
    if isinstance(raw, datetime):
        moment = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    else:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
    return moment <= datetime.now(timezone.utc)
