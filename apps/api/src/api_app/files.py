"""List files in a workspace. File text stays on the volume."""

from pathlib import Path

_SKIP = {".git", "__pycache__", ".pytest_cache", "node_modules"}
_LANGUAGES = {".py": "python", ".md": "markdown", ".json": "json", ".toml": "toml"}


def list_files(root: Path, limit: int) -> list[dict]:
    """Return path, size, and language. Stop after the configured cap."""
    if not root.is_dir():
        return []
    rows: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in _SKIP for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        language = _LANGUAGES.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "other")
        rows.append({"path": relative, "size_bytes": path.stat().st_size, "language": language})
        if len(rows) >= limit:
            break
    return rows
