"""Propose one small unified diff. This does not change the file."""

import hashlib
import uuid

from investigator_shared.errors import ToolFailure
from investigator_shared.paths import repository_root
from investigator_shared.registry import get_repository

from workspace_mcp.checks import check_diff_size, check_file_count, check_path
from workspace_mcp.config import get_settings
from workspace_mcp.logging import observed_tool
from workspace_mcp.patch import apply_to_text, parse_diff
from workspace_mcp.store import insert_proposal


@observed_tool
def propose_patch(repository_id: str, diff: str, session_id: str = "") -> dict:
    """Store a proposed diff. The file changes only after the owner approves it."""
    settings = get_settings()
    check_diff_size(diff, settings.max_diff_bytes)
    files = parse_diff(diff)
    paths = [item["path"] for item in files]
    check_file_count(paths, settings.max_files)
    root = repository_root(repository_id)
    planned = []
    for item in files:
        target = check_path(root, item["path"], settings.path_prefix)
        if not target.is_file():
            raise ToolFailure("FILE_NOT_FOUND", "Patch target does not exist.", False)
        original = target.read_text(encoding="utf-8")
        planned.append((target, apply_to_text(original, item["hunks"])))
    record = get_repository(repository_id)
    proposal_id = str(uuid.uuid4())
    digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    insert_proposal(
        proposal_id,
        repository_id,
        session_id,
        record.get("resolved_commit") or "",
        diff,
        digest,
    )
    return {
        "proposal_id": proposal_id,
        "status": "proposed",
        "files": paths,
        "diff": diff,
        "planned_bytes": [len(text.encode("utf-8")) for _, text in planned],
    }
