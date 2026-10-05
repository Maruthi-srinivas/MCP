"""Runtime settings for workspace edits."""

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def write_enabled() -> bool:
    """The three write tools are registered only when this is on."""
    return os.environ.get("WRITE_ENABLED", "0").strip() == "1"


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str
    max_files: int
    max_diff_bytes: int
    path_prefix: str


def get_settings() -> Settings:
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8005),
        database_url=os.environ.get("DATABASE_URL", "").strip(),
        max_files=_int_env("MAX_PATCH_FILES", 3),
        max_diff_bytes=_int_env("MAX_PATCH_BYTES", 16 * 1024),
        path_prefix=os.environ.get("PATCH_PATH_PREFIX", "").strip().strip("/"),
    )
