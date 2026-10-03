"""Load or rebuild the sibling index for one repository commit."""

import json
import time
from pathlib import Path

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.intelligence import python_index
from repository_mcp.workspace.ids import require_repository_id
from repository_mcp.workspace.paths import repository_root
from repository_mcp.workspace.registry import get_repository


def index_path(repository_id: str) -> Path:
    """JSON file beside the clone, not inside the git checkout."""
    require_repository_id(repository_id)
    return get_settings().workspace_root / f"{repository_id}.index.json"


def ensure_index(repository_id: str) -> dict:
    """Return the index for the stored commit, building it on first use."""
    record = get_repository(repository_id)
    commit_sha = record["resolved_commit"]
    path = index_path(repository_id)
    cached = _read_cached(path, commit_sha)
    if cached is not None:
        return cached
    root = repository_root(repository_id)
    built = python_index.build_index(root, commit_sha, get_settings(), time.monotonic())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return built


def require_python(index: dict) -> None:
    """Structural lookup needs at least one parsed Python file."""
    if index.get("python_files"):
        return
    raise ToolFailure(
        "UNSUPPORTED_LANGUAGE",
        "No Python files are available for structural analysis.",
        False,
    )


def _read_cached(path: Path, commit_sha: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("commit_sha") != commit_sha:
        return None
    if data.get("analyzer_version") != python_index.ANALYZER_VERSION:
        return None
    return data
