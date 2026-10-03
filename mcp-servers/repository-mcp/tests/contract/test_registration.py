import asyncio

from repository_mcp.server import mcp


def test_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = sorted(tool.name for tool in tools)
    assert names == [
        "clone_repository",
        "detect_project_type",
        "detect_services",
        "find_dependencies",
        "find_references",
        "find_symbol",
        "get_repository_info",
        "list_directory",
        "read_file",
        "search_code",
    ]
