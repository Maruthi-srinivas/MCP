"""Path jail, denylist, and size limits for a proposed diff."""

from investigator_shared.errors import ToolFailure
from investigator_shared.paths import resolve_inside

DENIED_NAMES = {
    ".env",
    "id_rsa",
    "credentials.json",
    "package-lock.json",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.sum",
}


def check_diff_size(diff: str, max_bytes: int) -> None:
    if not diff or not str(diff).strip():
        raise ToolFailure("PATCH_REJECTED", "Diff is empty.", False)
    if len(str(diff).encode("utf-8")) > max_bytes:
        raise ToolFailure("PATCH_REJECTED", "Diff is larger than the allowed size.", False)


def check_file_count(paths: list[str], max_files: int) -> None:
    if len(paths) > max_files:
        raise ToolFailure("PATCH_REJECTED", "Diff touches more files than allowed.", False)


def check_path(root, relative: str, prefix: str):
    """Reject traversal, secrets, and lockfiles. Return the file inside the workspace."""
    raw = str(relative).replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part in DENIED_NAMES or part.startswith(".env") for part in parts):
        raise ToolFailure("INVALID_PATH", "That path is not allowed in a patch.", False)
    if prefix and not (raw == prefix or raw.startswith(prefix + "/")):
        raise ToolFailure("INVALID_PATH", "Path is outside the allowed prefix.", False)
    return resolve_inside(root, raw)
