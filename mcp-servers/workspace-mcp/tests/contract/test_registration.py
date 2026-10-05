import asyncio

from mcp.server.fastmcp import FastMCP

from workspace_mcp.server import mcp, register_tools

TOOLS = (
    (
        "apply_patch",
        "Write the diff only when the approval row is still valid.",
        ("proposal_id", "approval_id"),
    ),
    (
        "preview_patch",
        "Return the stored diff and its status.",
        ("proposal_id",),
    ),
    (
        "propose_patch",
        "Store a proposed diff. The file changes only after the owner approves it.",
        ("repository_id", "diff", "session_id"),
    ),
)


def test_flag_on_registers_the_three_write_tools():
    tools = asyncio.run(mcp.list_tools())
    shapes = []
    for tool in tools:
        description = (tool.description or "").strip().splitlines()[0]
        arguments = tuple((tool.inputSchema or {}).get("properties") or ())
        shapes.append((tool.name, description, arguments))
    assert tuple(sorted(shapes)) == TOOLS


def test_flag_off_registers_nothing(monkeypatch):
    monkeypatch.setenv("WRITE_ENABLED", "0")
    fresh = FastMCP("workspace-off", stateless_http=True, json_response=True)
    register_tools(fresh)
    assert asyncio.run(fresh.list_tools()) == []
