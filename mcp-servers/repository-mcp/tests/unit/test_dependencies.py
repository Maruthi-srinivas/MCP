from repository_mcp.intelligence.dependencies import parse_requirement


def test_parse_requirement_skips_comments_and_flags():
    assert parse_requirement("fastapi==0.110.0") == {"name": "fastapi", "version": "0.110.0"}
    assert parse_requirement("uvicorn") == {"name": "uvicorn", "version": None}
    assert parse_requirement("# comment") is None
    assert parse_requirement("-r requirements-dev.txt") is None
    assert parse_requirement("--extra-index-url https://example.com") is None
