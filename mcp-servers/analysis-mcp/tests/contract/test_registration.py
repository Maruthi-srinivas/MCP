import asyncio

from analysis_mcp.server import mcp


def test_only_analysis_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = sorted(tool.name for tool in tools)
    assert names == [
        "analyze_code",
        "build_dependency_graph",
        "detect_api_endpoints",
        "detect_database_access",
        "detect_entrypoints",
        "detect_external_services",
        "find_classes",
        "find_functions",
        "find_imports",
    ]
