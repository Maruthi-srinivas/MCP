"""Stable repository ids. The hash matches Repository MCP so a job can be polled before clone returns."""

import hashlib
import re
from pathlib import Path

_GITHUB = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def repository_identity(url: str, ref: str | None) -> tuple[str, str, str, str]:
    """Return repository_id, canonical url, owner, and name."""
    raw = url.strip()
    match = _GITHUB.match(raw)
    if match:
        owner = match.group("owner").lower()
        name = match.group("name").lower()
        canonical = f"https://github.com/{owner}/{name}"
    else:
        path = Path(raw.removeprefix("file://")).resolve() if raw.startswith("file://") else Path(raw).resolve()
        canonical = path.as_uri()
        owner = "local"
        name = path.name or "repository"
    ref_key = ref or "HEAD"
    digest = hashlib.sha256(f"{canonical}\n{ref_key}".encode("utf-8")).hexdigest()[:16]
    return f"repo_{digest}", canonical, owner, name
