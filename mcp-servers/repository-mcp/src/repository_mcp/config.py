"""Runtime settings. Every value comes from the environment so the image stays configurable."""

from dataclasses import dataclass
import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Limits and paths for one process."""

    workspace_root: Path
    host: str
    port: int
    max_read_lines: int
    max_file_bytes: int
    max_search_hits: int
    max_directory_entries: int
    clone_timeout_seconds: int
    tool_timeout_seconds: int
    max_python_files: int
    max_symbols: int
    max_references: int
    index_timeout_seconds: int
    git_clone_depth: int
    github_token: str | None
    allow_local_git: bool
    resource_max_chars: int


def get_settings() -> Settings:
    """Read settings on each call so tests can change the environment."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    return Settings(
        workspace_root=Path(os.environ.get("WORKSPACE_ROOT", "/workspaces")),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8000),
        max_read_lines=_int_env("MAX_READ_LINES", 200),
        max_file_bytes=_int_env("MAX_FILE_BYTES", 1_048_576),
        max_search_hits=_int_env("MAX_SEARCH_HITS", 50),
        max_directory_entries=_int_env("MAX_DIRECTORY_ENTRIES", 200),
        clone_timeout_seconds=_int_env("CLONE_TIMEOUT_SECONDS", 60),
        tool_timeout_seconds=_int_env("TOOL_TIMEOUT_SECONDS", 30),
        max_python_files=_int_env("MAX_PYTHON_FILES", 200),
        max_symbols=_int_env("MAX_SYMBOLS", 500),
        max_references=_int_env("MAX_REFERENCES", 50),
        index_timeout_seconds=_int_env("INDEX_TIMEOUT_SECONDS", 30),
        git_clone_depth=_int_env("GIT_CLONE_DEPTH", 50),
        github_token=token or None,
        allow_local_git=os.environ.get("ALLOW_LOCAL_GIT", "").strip() == "1",
        resource_max_chars=_int_env("RESOURCE_MAX_CHARS", 8000),
    )
