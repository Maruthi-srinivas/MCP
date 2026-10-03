"""List one directory. The listing is not recursive."""

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root, resolve_inside


@observed_tool
def list_directory(repository_id: str, path: str = ".") -> dict:
    """List files and directories directly inside path, up to the configured cap."""
    root = repository_root(repository_id)
    directory = resolve_inside(root, path)
    if not directory.is_dir():
        raise ToolFailure("INVALID_PATH", "Path is not a directory.", False)

    names = sorted(entry.name for entry in directory.iterdir() if entry.name != ".git")
    directories: list[str] = []
    files: list[str] = []
    for name in names:
        child = directory / name
        if child.is_dir() and not child.is_symlink():
            directories.append(name)
        elif child.is_file() or child.is_symlink():
            files.append(name)

    limit = get_settings().max_directory_entries
    combined = [("dir", name) for name in directories] + [("file", name) for name in files]
    truncated = len(combined) > limit
    kept = combined[:limit]
    return {
        "repository_id": repository_id,
        "path": _relative(root, directory),
        "directories": [name for kind, name in kept if kind == "dir"],
        "files": [name for kind, name in kept if kind == "file"],
        "truncated": truncated,
    }


def _relative(root, directory) -> str:
    relative = directory.resolve().relative_to(root.resolve())
    text = relative.as_posix()
    return "." if text == "" else text
