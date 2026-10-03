import logging

from repository_mcp.tools.clone_repository import clone_repository
from repository_mcp.tools.get_repository_info import get_repository_info
from repository_mcp.tools.list_directory import list_directory
from repository_mcp.tools.read_file import read_file
from repository_mcp.tools.search_code import search_code
from tests.support import git


def test_read_list_and_search(seeded):
    listing = list_directory(seeded, ".")
    assert "README.md" in listing["files"]
    assert "src" in listing["directories"]
    assert listing["truncated"] is False

    body = read_file(seeded, "src/app.py")
    assert "hello fixture" in body["content"]
    assert body["truncated"] is False
    assert body["start_line"] == 1

    found = search_code(seeded, "hello fixture")
    paths = {match["path"] for match in found["matches"]}
    assert "README.md" in paths
    assert any(match["line"] >= 1 and match["snippet"] for match in found["matches"])


def test_unknown_repository():
    missing = "repo_" + "ab" * 8
    result = get_repository_info(missing)
    assert result["error"]["code"] == "REPOSITORY_NOT_FOUND"
    assert result["error"]["retryable"] is False
    assert result["error"]["request_id"].startswith("req_")


def test_traversal_and_missing_file(seeded):
    escaped = read_file(seeded, "../../etc/passwd")
    assert escaped["error"]["code"] == "INVALID_PATH"
    missing = read_file(seeded, "src/missing.py")
    assert missing["error"]["code"] == "FILE_NOT_FOUND"


def test_large_file_and_truncation(seeded, monkeypatch):
    from pathlib import Path

    from repository_mcp.workspace.registry import get_repository

    root = Path(get_repository(seeded)["workspace_path"])
    huge = root / "huge.txt"
    huge.write_bytes(b"x" * (1_048_576 + 1))
    too_big = read_file(seeded, "huge.txt")
    assert too_big["error"]["code"] == "FILE_TOO_LARGE"

    lines = root / "long.txt"
    lines.write_text("\n".join(f"line {index}" for index in range(1, 11)), encoding="utf-8")
    monkeypatch.setenv("MAX_READ_LINES", "2")
    window = read_file(seeded, "long.txt")
    assert window["truncated"] is True
    assert window["content"].count("\n") == 1
    assert window["total_lines"] == 10


def test_directory_cap(seeded, monkeypatch):
    from pathlib import Path

    from repository_mcp.workspace.registry import get_repository

    root = Path(get_repository(seeded)["workspace_path"])
    for index in range(5):
        (root / f"extra_{index}.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("MAX_DIRECTORY_ENTRIES", "2")
    listing = list_directory(seeded, ".")
    assert listing["truncated"] is True
    assert len(listing["directories"]) + len(listing["files"]) == 2


def test_search_hit_cap(seeded, monkeypatch):
    from pathlib import Path

    from repository_mcp.workspace.registry import get_repository

    root = Path(get_repository(seeded)["workspace_path"])
    (root / "many.txt").write_text("\n".join(["needle"] * 10), encoding="utf-8")
    monkeypatch.setenv("MAX_SEARCH_HITS", "3")
    found = search_code(seeded, "needle", "many.txt")
    assert len(found["matches"]) == 3
    assert found["truncated"] is True


def test_clone_local_repository_is_stable(workspace):
    source = workspace / "source"
    source.mkdir()
    (source / "README.md").write_text("local clone\n", encoding="utf-8")
    git(source, "-c", "init.defaultBranch=main", "init")
    git(source, "add", ".")
    git(source, "commit", "-m", "init")

    first = clone_repository(str(source))
    assert first["status"] == "ready"
    assert len(first["resolved_commit"]) == 40

    (source / "README.md").write_text("local clone\nupdated\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "update")
    second = clone_repository(str(source))
    assert second["repository_id"] == first["repository_id"]
    assert second["resolved_commit"] != first["resolved_commit"]

    info = get_repository_info(first["repository_id"])
    assert info["resolved_commit"] == second["resolved_commit"]
    listed = list_directory(first["repository_id"], ".")
    assert "README.md" in listed["files"]


def test_clone_rejects_public_non_github_url():
    result = clone_repository("https://example.com/not/github")
    assert result["error"]["code"] == "INVALID_REPOSITORY_URL"


def test_tool_log_has_no_token(seeded, caplog, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret-token")
    caplog.set_level(logging.INFO)
    search_code(seeded, "hello fixture")
    text = "\n".join(record.message for record in caplog.records)
    assert "search_code" in text
    assert "success" in text
    assert "super-secret-token" not in text
