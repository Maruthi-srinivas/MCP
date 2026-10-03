import shutil
from pathlib import Path

import pytest

from repository_mcp.intelligence import python_index
from repository_mcp.intelligence.index import index_path
from repository_mcp.tools.detect_project_type import detect_project_type
from repository_mcp.tools.detect_services import detect_services
from repository_mcp.tools.find_dependencies import find_dependencies
from repository_mcp.tools.find_references import find_references
from repository_mcp.tools.find_symbol import find_symbol
from repository_mcp.workspace.ids import make_repository_id
from repository_mcp.workspace.registry import get_repository, save_repository
from tests.support import git

FIXTURE = Path(__file__).parents[1] / "fixtures" / "fastapi_app"


@pytest.fixture
def fastapi_repo(workspace):
    repository_id = make_repository_id("https://github.com/example/fastapi-app", "HEAD")
    destination = workspace / repository_id
    shutil.copytree(FIXTURE, destination)
    git(destination, "-c", "init.defaultBranch=main", "init")
    git(destination, "add", ".")
    git(destination, "commit", "-m", "init")
    sha = git(destination, "rev-parse", "HEAD")
    save_repository(
        {
            "repository_id": repository_id,
            "url": "https://github.com/example/fastapi-app",
            "owner": "example",
            "name": "fastapi-app",
            "ref": None,
            "resolved_commit": sha,
            "workspace_path": str(destination),
            "status": "ready",
        }
    )
    return repository_id


def test_project_type_dependencies_symbol_and_references(fastapi_repo):
    project = detect_project_type(fastapi_repo)
    assert "Python" in project["languages"]
    assert "JavaScript" in project["languages"]
    assert "FastAPI" in project["frameworks"]
    assert any(item["path"] == "notes.js" for item in project["warnings"])

    dependencies = find_dependencies(fastapi_repo)
    found = {(item["name"], item["version"], item["source_file"]) for item in dependencies["dependencies"]}
    assert ("fastapi", "0.110.0", "requirements.txt") in found
    assert ("httpx", "0.28.1", "requirements-dev.txt") in found
    assert ("uvicorn", "0.34.2", "pyproject.toml") in found

    symbol = find_symbol(fastapi_repo, "create_user")
    assert symbol["definitions"] == [
        {
            "name": "create_user",
            "kind": "function",
            "path": "app/users/service.py",
            "start_line": 1,
            "end_line": 2,
        }
    ]

    references = find_references(fastapi_repo, "create_user")
    paths = {item["path"] for item in references["references"]}
    assert "app/main.py" in paths
    alias_lines = [item for item in references["references"] if item["path"] == "app/alias_user.py"]
    assert len(alias_lines) == 1
    assert "create_user" in alias_lines[0]["snippet"]
    assert "make_user()" not in alias_lines[0]["snippet"]

    services = detect_services(fastapi_repo)
    kinds = {(item["path"], item["reason"]) for item in services["services"]}
    assert ("app", "package") in kinds
    assert ("app/main.py", "entrypoint") in kinds


def test_missing_symbol(fastapi_repo):
    missing = find_symbol(fastapi_repo, "does_not_exist")
    assert missing["error"]["code"] == "SYMBOL_NOT_FOUND"
    assert missing["error"]["retryable"] is False


def test_index_is_reused_until_commit_changes(fastapi_repo, monkeypatch):
    find_symbol(fastapi_repo, "create_user")
    original = python_index.build_index

    def fail_rebuild(*_args, **_kwargs):
        raise AssertionError("index rebuilt")

    monkeypatch.setattr(python_index, "build_index", fail_rebuild)
    again = find_symbol(fastapi_repo, "create_user")
    assert again["definitions"][0]["path"] == "app/users/service.py"

    monkeypatch.setattr(python_index, "build_index", original)
    record = get_repository(fastapi_repo)
    record["resolved_commit"] = "a" * 40
    save_repository(record)
    calls = {"count": 0}

    def counting(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(python_index, "build_index", counting)
    find_symbol(fastapi_repo, "create_user")
    assert calls["count"] == 1
    stored = index_path(fastapi_repo).read_text(encoding="utf-8")
    assert "a" * 40 in stored


def test_syntax_error_is_a_warning(fastapi_repo):
    record = get_repository(fastapi_repo)
    root = Path(record["workspace_path"])
    (root / "broken.py").write_text("def (\n", encoding="utf-8")
    record["resolved_commit"] = "b" * 40
    save_repository(record)
    symbol = find_symbol(fastapi_repo, "create_user")
    assert symbol["definitions"][0]["path"] == "app/users/service.py"
    assert any(item["path"] == "broken.py" and "Syntax error" in item["message"] for item in symbol["warnings"])


def test_no_python_is_unsupported(workspace):
    repository_id = make_repository_id("https://github.com/example/js-only", "HEAD")
    destination = workspace / repository_id
    destination.mkdir()
    (destination / "notes.js").write_text("export const note = 1;\n", encoding="utf-8")
    save_repository(
        {
            "repository_id": repository_id,
            "url": "https://github.com/example/js-only",
            "owner": "example",
            "name": "js-only",
            "ref": None,
            "resolved_commit": "c" * 40,
            "workspace_path": str(destination),
            "status": "ready",
        }
    )
    result = find_symbol(repository_id, "create_user")
    assert result["error"]["code"] == "UNSUPPORTED_LANGUAGE"
