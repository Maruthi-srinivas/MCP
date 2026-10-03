from repository_mcp.errors import ToolFailure
from repository_mcp.workspace.ids import make_repository_id, parse_repository_url, validate_ref


def test_github_url_is_canonical_and_stable():
    first = parse_repository_url("https://github.com/Org/Name.git", allow_local=False)
    second = parse_repository_url("https://github.com/org/name", allow_local=False)
    assert first.canonical_url == "https://github.com/org/name"
    assert first == second
    assert make_repository_id(first.canonical_url, "HEAD") == make_repository_id(second.canonical_url, "HEAD")
    assert make_repository_id(first.canonical_url, "HEAD") != make_repository_id(first.canonical_url, "dev")


def test_rejects_non_github_url():
    try:
        parse_repository_url("https://gitlab.com/org/name", allow_local=False)
    except ToolFailure as failure:
        assert failure.code == "INVALID_REPOSITORY_URL"
    else:
        raise AssertionError("expected INVALID_REPOSITORY_URL")


def test_rejects_url_with_userinfo():
    try:
        parse_repository_url("https://user:token@github.com/org/name", allow_local=False)
    except ToolFailure as failure:
        assert failure.code == "INVALID_REPOSITORY_URL"
    else:
        raise AssertionError("expected INVALID_REPOSITORY_URL")


def test_local_url_requires_opt_in(tmp_path):
    try:
        parse_repository_url(str(tmp_path), allow_local=False)
    except ToolFailure as failure:
        assert failure.code == "INVALID_REPOSITORY_URL"
    else:
        raise AssertionError("expected INVALID_REPOSITORY_URL")
    parsed = parse_repository_url(str(tmp_path), allow_local=True)
    assert parsed.kind == "local"


def test_ref_rules():
    assert validate_ref("feature/login") == "feature/login"
    assert validate_ref("a" * 40) == "a" * 40
    try:
        validate_ref("../main")
    except ToolFailure as failure:
        assert failure.code == "CLONE_FAILED"
    else:
        raise AssertionError("expected CLONE_FAILED")
