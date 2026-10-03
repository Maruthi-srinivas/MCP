import asyncio

from git_mcp.server import mcp


def test_only_read_only_git_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = sorted(tool.name for tool in tools)
    assert names == [
        "compare_branches",
        "find_introduced_change",
        "get_branches",
        "get_commit",
        "get_commits",
        "get_diff",
        "get_file_history",
        "get_git_status",
    ]
    forbidden = {"commit", "push", "reset", "checkout", "merge", "rebase", "clean"}
    assert forbidden.isdisjoint(names)
