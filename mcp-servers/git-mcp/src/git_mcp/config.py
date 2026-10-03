"""Runtime settings for the read-only Git MCP."""

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    host: str
    port: int
    tool_timeout_seconds: int
    default_page_size: int
    max_page_size: int
    max_diff_lines: int
    max_branches: int


def get_settings() -> Settings:
    return Settings(
        workspace_root=Path(os.environ.get("WORKSPACE_ROOT", "/workspaces")),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8001),
        tool_timeout_seconds=_int_env("TOOL_TIMEOUT_SECONDS", 30),
        default_page_size=_int_env("DEFAULT_PAGE_SIZE", 20),
        max_page_size=_int_env("MAX_PAGE_SIZE", 50),
        max_diff_lines=_int_env("MAX_DIFF_LINES", 200),
        max_branches=_int_env("MAX_BRANCHES", 50),
    )


def bounded_page(page: int, page_size: int | None) -> tuple[int, int]:
    """Return a positive page and a page size that cannot exceed the cap."""
    from investigator_shared.errors import ToolFailure

    settings = get_settings()
    size = settings.default_page_size if page_size is None else page_size
    if page < 1 or size < 1:
        raise ToolFailure("INTERNAL_ERROR", "page and page_size must be positive.", False)
    return page, min(size, settings.max_page_size)
