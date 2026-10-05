"""Local fixtures added in V1.0. service_app stays unchanged."""

import shutil
from pathlib import Path

from repository_mcp.tools.find_symbol import find_symbol
from repository_mcp.tools.read_file import read_file
from repository_mcp.workspace.ids import make_repository_id
from repository_mcp.workspace.registry import save_repository
from tests.support import git

ROOT = Path(__file__).parents[1] / "fixtures"


def _seed(workspace: Path, fixture: str, url: str) -> str:
    repository_id = make_repository_id(url, "HEAD")
    destination = workspace / repository_id
    shutil.copytree(ROOT / fixture, destination)
    git(destination, "-c", "init.defaultBranch=main", "init")
    git(destination, "add", ".")
    git(destination, "commit", "-m", "init")
    sha = git(destination, "rev-parse", "HEAD")
    save_repository(
        {
            "repository_id": repository_id,
            "url": url,
            "owner": "example",
            "name": fixture,
            "ref": None,
            "resolved_commit": sha,
            "workspace_path": str(destination),
            "status": "ready",
        }
    )
    return repository_id


def test_multi_module_symbol_resolves(workspace):
    repository_id = _seed(workspace, "multi_module", "https://github.com/example/multi-module")
    symbol = find_symbol(repository_id, "load_note")
    assert symbol["definitions"][0]["path"] == "pkg/reader.py"


def test_nested_read_truncates_and_rejects_parent_paths(workspace):
    repository_id = _seed(workspace, "nested_read", "https://github.com/example/nested-read")
    window = read_file(repository_id, "deep/nest/long.txt")
    assert window["truncated"] is True
    assert window["total_lines"] > 200
    escaped = read_file(repository_id, "../../etc/passwd")
    assert escaped["error"]["code"] == "INVALID_PATH"
