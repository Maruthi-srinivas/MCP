"""Reject paths the file route must not pass to read_file."""


def unsafe_path(path: str) -> bool:
    """True for an absolute path, a parent segment, or a .git segment."""
    raw = path.strip()
    if not raw:
        return True
    if raw.startswith("/") or raw.startswith("\\") or (len(raw) >= 2 and raw[1] == ":"):
        return True
    parts = [part for part in raw.replace("\\", "/").split("/") if part not in ("", ".")]
    return any(part in {"..", ".git"} or ":" in part for part in parts)
