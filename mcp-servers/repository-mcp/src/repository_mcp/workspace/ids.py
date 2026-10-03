"""Normalize a repository URL and derive a stable repository id."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from repository_mcp.errors import ToolFailure

_GITHUB = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_REF = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
_REPO_ID = re.compile(r"^repo_[0-9a-f]{16}$")


@dataclass(frozen=True)
class RepositoryTarget:
    """Where git should clone, and the identity used for the stable id."""

    clone_url: str
    canonical_url: str
    owner: str
    name: str
    kind: str


def parse_repository_url(repository_url: str, *, allow_local: bool) -> RepositoryTarget:
    """Accept a public GitHub HTTPS URL. Local paths only when tests opt in."""
    raw = repository_url.strip()
    if not raw or "@" in raw or raw.startswith("-"):
        raise ToolFailure("INVALID_REPOSITORY_URL", "Repository URL is not a public GitHub HTTPS URL.", False)

    match = _GITHUB.match(raw)
    if match:
        owner = match.group("owner").lower()
        name = match.group("name").lower()
        canonical = f"https://github.com/{owner}/{name}"
        return RepositoryTarget(canonical, canonical, owner, name, "github")

    if allow_local:
        local = _parse_local(raw)
        if local is not None:
            return local

    raise ToolFailure(
        "INVALID_REPOSITORY_URL",
        "Repository URL must look like https://github.com/owner/name.",
        False,
    )


def _parse_local(raw: str) -> RepositoryTarget | None:
    if raw.startswith("file://"):
        path = Path(raw.removeprefix("file://"))
    elif raw.startswith("/"):
        path = Path(raw)
    else:
        return None
    resolved = path.resolve()
    return RepositoryTarget(
        clone_url=str(resolved),
        canonical_url=resolved.as_uri(),
        owner="local",
        name=resolved.name or "repository",
        kind="local",
    )


def validate_ref(ref: str) -> str:
    """Allow a branch, a tag, or a full commit SHA. Reject anything git could misread."""
    if _SHA.match(ref):
        return ref
    if (
        not _REF.match(ref)
        or ref.startswith("/")
        or ref.endswith("/")
        or ref.startswith("-")
        or ".." in ref
        or "//" in ref
    ):
        raise ToolFailure(
            "CLONE_FAILED",
            "ref must be a branch, a tag, or a full 40-character commit SHA.",
            False,
        )
    return ref


def is_commit_sha(ref: str) -> bool:
    return bool(_SHA.match(ref))


def make_repository_id(canonical_url: str, ref_key: str) -> str:
    """Same URL and requested ref always map to the same id."""
    digest = hashlib.sha256(f"{canonical_url}\n{ref_key}".encode("utf-8")).hexdigest()[:16]
    return f"repo_{digest}"


def require_repository_id(repository_id: str) -> str:
    if not _REPO_ID.match(repository_id):
        raise ToolFailure("REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return repository_id
