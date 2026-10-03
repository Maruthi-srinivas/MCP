"""Shared fixtures. Git commands use -c so they do not write a git config file."""

import shutil
from pathlib import Path

import pytest

from repository_mcp.workspace.ids import make_repository_id
from repository_mcp.workspace.registry import save_repository
from tests.support import git

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_repo"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ALLOW_LOCAL_GIT", "1")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return tmp_path


@pytest.fixture
def seeded(workspace):
    """Register the tiny fixture as if clone_repository had imported it."""
    repository_id = make_repository_id("https://github.com/example/tiny", "HEAD")
    destination = workspace / repository_id
    shutil.copytree(FIXTURE, destination)
    git(destination, "-c", "init.defaultBranch=main", "init")
    git(destination, "add", ".")
    git(destination, "commit", "-m", "init")
    sha = git(destination, "rev-parse", "HEAD")
    save_repository(
        {
            "repository_id": repository_id,
            "url": "https://github.com/example/tiny",
            "owner": "example",
            "name": "tiny",
            "ref": None,
            "resolved_commit": sha,
            "workspace_path": str(destination),
            "status": "ready",
        }
    )
    return repository_id
