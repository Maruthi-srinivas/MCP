"""Runtime settings for Analysis MCP."""

import os
from dataclasses import dataclass
from pathlib import Path

from investigator_shared.errors import ToolFailure


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
    analysis_timeout_seconds: int
    max_python_files: int
    max_file_bytes: int
    max_functions: int
    max_classes: int
    max_endpoints: int
    max_edges: int
    max_hints: int
    default_page_size: int
    max_page_size: int
    resource_max_chars: int


def get_settings() -> Settings:
    return Settings(
        workspace_root=Path(os.environ.get("WORKSPACE_ROOT", "/workspaces")),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8002),
        analysis_timeout_seconds=_int_env("ANALYSIS_TIMEOUT", 30),
        max_python_files=_int_env("MAX_PYTHON_FILES", 200),
        max_file_bytes=_int_env("MAX_FILE_BYTES", 1048576),
        max_functions=_int_env("MAX_FUNCTIONS", 500),
        max_classes=_int_env("MAX_CLASSES", 500),
        max_endpoints=_int_env("MAX_ENDPOINTS", 200),
        max_edges=_int_env("MAX_EDGES", 500),
        max_hints=_int_env("MAX_HINTS", 200),
        default_page_size=_int_env("DEFAULT_PAGE_SIZE", 20),
        max_page_size=_int_env("MAX_PAGE_SIZE", 50),
        resource_max_chars=_int_env("RESOURCE_MAX_CHARS", 8000),
    )


def bounded_page(page: int, page_size: int | None) -> tuple[int, int]:
    """Return a positive page and a page size that cannot exceed the cap."""
    settings = get_settings()
    size = settings.default_page_size if page_size is None else page_size
    if page < 1 or size < 1:
        raise ToolFailure("INTERNAL_ERROR", "page and page_size must be positive.", False)
    return page, min(size, settings.max_page_size)
