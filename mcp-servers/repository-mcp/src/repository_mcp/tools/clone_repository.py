"""Import a public GitHub repository into an isolated workspace."""

from repository_mcp.config import get_settings
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.clone import sync_workspace
from repository_mcp.workspace.ids import make_repository_id, parse_repository_url, validate_ref
from repository_mcp.workspace.registry import save_repository


@observed_tool
def clone_repository(repository_url: str, ref: str | None = None) -> dict:
    """Clone or refresh one public GitHub repository at a branch, tag, or commit SHA.

    The same URL and ref always return the same repository_id. A later call
    fetches that ref again instead of creating a second workspace.
    """
    settings = get_settings()
    target = parse_repository_url(repository_url, allow_local=settings.allow_local_git)
    if ref is not None:
        ref = validate_ref(ref)
    ref_key = ref or "HEAD"
    repository_id = make_repository_id(target.canonical_url, ref_key)
    destination = settings.workspace_root / repository_id
    resolved_commit = sync_workspace(target, ref, destination, settings)
    record = {
        "repository_id": repository_id,
        "url": target.canonical_url,
        "owner": target.owner,
        "name": target.name,
        "ref": ref,
        "resolved_commit": resolved_commit,
        "workspace_path": str(destination),
        "status": "ready",
    }
    save_repository(record)
    return {
        "repository_id": repository_id,
        "workspace_path": str(destination),
        "resolved_commit": resolved_commit,
        "status": "ready",
    }
