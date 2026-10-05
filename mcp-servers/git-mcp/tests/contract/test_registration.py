import asyncio

from git_mcp.server import mcp

TOOLS = (
    ("compare_branches", "Return both tip SHAs, ahead/behind counts, and a bounded list of changed paths.", ("repository_id", "base", "head")),
    ("find_introduced_change", "Use git log -L for a single line. This does not search by symbol name.", ("repository_id", "path", "line")),
    ("get_branches", "Return branch names and tip SHAs. This does not fetch from the network.", ("repository_id",)),
    ("get_commit", "Return the SHA, author, date, and subject for a branch, tag, or full SHA.", ("repository_id", "ref")),
    ("get_commits", "Return SHA, author, date, and subject for one page of commits.", ("repository_id", "ref", "page", "page_size")),
    ("get_diff", "Diff base and head. The result includes both resolved SHAs and cuts long patches.", ("repository_id", "base", "head")),
    ("get_file_history", "List commits that touched path. Each item has a SHA, author, date, and subject.", ("repository_id", "path", "ref", "page", "page_size")),
    ("get_git_status", "Return HEAD, the branch name, and porcelain entries. A clean clone has no entries.", ("repository_id",)),
)

PROMPTS = (("investigate_change", ("repository_id", "path")),)


def test_only_read_only_git_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    shapes = []
    for tool in tools:
        description = (tool.description or "").strip().splitlines()[0]
        arguments = tuple((tool.inputSchema or {}).get("properties") or ())
        shapes.append((tool.name, description, arguments))
    assert tuple(sorted(shapes)) == TOOLS
    forbidden = {"commit", "push", "reset", "checkout", "merge", "rebase", "clean"}
    assert forbidden.isdisjoint(tool.name for tool in tools)


def test_prompt_is_registered():
    prompts = asyncio.run(mcp.list_prompts())
    shapes = tuple(sorted((item.name, tuple(arg.name for arg in item.arguments or [])) for item in prompts))
    assert shapes == PROMPTS
