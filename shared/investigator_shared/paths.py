"""Keep every user-supplied path inside one repository workspace."""

from pathlib import Path

from investigator_shared.errors import ToolFailure
from investigator_shared.registry import get_repository, require_repository_id, workspace_root


def repository_root(repository_id: str) -> Path:
    """Resolve the workspace directory recorded for this repository."""
    require_repository_id(repository_id)
    record = get_repository(repository_id)
    root = Path(record["workspace_path"]).resolve()
    allowed = workspace_root().resolve()
    if not _is_inside(root, allowed):
        raise ToolFailure("INVALID_PATH", "Workspace is outside the configured root.", False)
    if not root.is_dir():
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Workspace directory is missing.", False)
    return root


def resolve_inside(root: Path, user_path: str) -> Path:
    """Normalize a relative path and reject traversal, including symlink escape."""
    if user_path is None or not str(user_path).strip():
        raise ToolFailure("INVALID_PATH", "Path is required.", False)
    raw = str(user_path).strip()
    if raw.startswith("/") or raw.startswith("\\") or (len(raw) >= 2 and raw[1] == ":"):
        raise ToolFailure("INVALID_PATH", "Absolute paths are not allowed.", False)

    normalized = raw.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts and normalized not in (".", "./"):
        raise ToolFailure("INVALID_PATH", "Path is empty.", False)
    if any(part in {"..", ".git"} or ":" in part for part in parts):
        raise ToolFailure("INVALID_PATH", "Path escapes the repository or enters .git.", False)

    candidate = (root.joinpath(*parts)).resolve() if parts else root.resolve()
    if not _is_inside(candidate, root.resolve()):
        raise ToolFailure("INVALID_PATH", "Path escapes the repository workspace.", False)
    return candidate


def relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
