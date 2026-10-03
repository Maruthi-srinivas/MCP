import pytest

from repository_mcp.errors import ToolFailure
from repository_mcp.workspace.paths import resolve_inside


def test_rejects_parent_traversal(tmp_path):
    with pytest.raises(ToolFailure) as caught:
        resolve_inside(tmp_path, "../../etc/passwd")
    assert caught.value.code == "INVALID_PATH"


def test_rejects_absolute_path(tmp_path):
    with pytest.raises(ToolFailure) as caught:
        resolve_inside(tmp_path, "/etc/passwd")
    assert caught.value.code == "INVALID_PATH"


def test_rejects_git_directory(tmp_path):
    with pytest.raises(ToolFailure) as caught:
        resolve_inside(tmp_path, ".git/config")
    assert caught.value.code == "INVALID_PATH"


def test_rejects_symlink_escape(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "leak.txt"
    link.symlink_to(outside)
    with pytest.raises(ToolFailure) as caught:
        resolve_inside(root, "leak.txt")
    assert caught.value.code == "INVALID_PATH"


def test_allows_nested_file(tmp_path):
    root = tmp_path / "repo"
    nested = root / "src"
    nested.mkdir(parents=True)
    target = nested / "app.py"
    target.write_text("x", encoding="utf-8")
    assert resolve_inside(root, "src/app.py") == target.resolve()
