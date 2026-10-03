"""git-mcp serves one prompt and no resources."""

import asyncio

from git_mcp.prompts import investigate_change
from git_mcp.server import mcp


def test_investigate_change_is_listed_and_names_tools():
    prompts = asyncio.run(mcp.list_prompts())
    names = sorted(prompt.name for prompt in prompts)
    assert names == ["investigate_change"]
    text = investigate_change("repo_x", "app/main.py")
    assert "get_file_history" in text
    assert "get_commits" in text
    assert "get_diff" in text
    templates = asyncio.run(mcp.list_resource_templates())
    assert list(templates) == []
