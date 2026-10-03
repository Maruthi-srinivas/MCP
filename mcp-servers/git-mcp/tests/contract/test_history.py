"""Three commits that change notes.txt. The git repository is created in the test."""

import hashlib
from pathlib import Path

import pytest

from git_mcp.tools.compare_branches import compare_branches
from git_mcp.tools.find_introduced_change import find_introduced_change
from git_mcp.tools.get_commits import get_commits
from git_mcp.tools.get_diff import get_diff
from git_mcp.tools.get_file_history import get_file_history
from git_mcp.tools.get_git_status import get_git_status
from tests.conftest import save_record
from tests.support import git

FIXTURE = Path(__file__).parents[1] / "fixtures" / "history_repo"


def _repository_id() -> str:
    digest = hashlib.sha256(b"https://github.com/example/history\nHEAD").hexdigest()[:16]
    return f"repo_{digest}"


@pytest.fixture
def history(workspace):
    repository_id = _repository_id()
    destination = workspace / repository_id
    destination.mkdir()
    git(destination, "-c", "init.defaultBranch=main", "init")
    versions = [("one\n", "add one"), ("two\n", "change to two"), ("three\n", "change to three")]
    for text, message in versions:
        (destination / "notes.txt").write_text(text, encoding="utf-8")
        git(destination, "add", "notes.txt")
        git(destination, "commit", "-m", message)
    assert (destination / "notes.txt").read_text(encoding="utf-8") == FIXTURE.joinpath("notes.txt").read_text(encoding="utf-8")
    oldest_first = git(destination, "log", "--reverse", "--format=%H").splitlines()
    git(destination, "branch", "start", oldest_first[0])
    save_record(repository_id, destination, oldest_first[-1])
    return repository_id, oldest_first


def test_history_diff_and_compare(history):
    repository_id, shas = history
    status = get_git_status(repository_id)
    assert status["clean"] is True
    assert status["head_sha"] == shas[-1]

    file_commits = get_file_history(repository_id, "notes.txt")
    assert [item["sha"] for item in file_commits["commits"]] == list(reversed(shas))

    listed = get_commits(repository_id, ref="main", page=1)
    assert {item["sha"] for item in listed["commits"]} == set(shas)

    changed = get_diff(repository_id, shas[0], shas[1])
    assert changed["base_sha"] == shas[0]
    assert changed["head_sha"] == shas[1]
    assert "two" in changed["patch"]
    assert changed["truncated"] is False

    compared = compare_branches(repository_id, "start", "main")
    assert compared["base_sha"] == shas[0]
    assert compared["head_sha"] == shas[-1]
    assert compared["ahead"] == 2
    assert any(item["path"] == "notes.txt" for item in compared["changed_paths"])

    introduced = find_introduced_change(repository_id, "notes.txt", 1)
    assert introduced["sha"] == shas[-1]


def test_unknown_ref_and_traversal(history):
    repository_id, _shas = history
    missing = get_commits(repository_id, ref="no-such-branch")
    assert missing["error"]["code"] == "GIT_REF_NOT_FOUND"
    assert missing["error"]["retryable"] is False
    escaped = get_file_history(repository_id, "../../etc/passwd")
    assert escaped["error"]["code"] == "INVALID_PATH"
