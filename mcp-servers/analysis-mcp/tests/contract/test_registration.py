import asyncio

from analysis_mcp.server import mcp

TOOLS = (
    ("analyze_code", "Return commit, analyzer version, counts, and warnings. Lists stay on the other tools.", ("repository_id",)),
    ("build_dependency_graph", "Return nodes and edges. A call edge is inferred because it is a name match, not a runtime trace.", ("repository_id",)),
    ("detect_api_endpoints", "Return HTTP routes. Each item has a framework, method, path, file, and line.", ("repository_id",)),
    ("detect_database_access", "Return hints with file and line. A hint is not proof that a query ran.", ("repository_id",)),
    ("detect_entrypoints", "List likely process entrypoints with a path, line, and reason.", ("repository_id",)),
    ("detect_external_services", "Return httpx, requests, urllib.request, and aiohttp calls. A missing URL is inferred.", ("repository_id",)),
    ("find_classes", "List classes. An empty name returns a page. No match is an empty list.", ("repository_id", "name", "page", "page_size")),
    ("find_functions", "List functions. An empty name returns a page. No match is an empty list.", ("repository_id", "name", "page", "page_size")),
    ("find_imports", "List imports. name matches the module or an imported name. No match is an empty list.", ("repository_id", "name", "page", "page_size")),
    ("search_symbols", "Return the closest symbols for a query. Each match has a path, line, and snippet.", ("repository_id", "query")),
)

PROMPTS = (
    ("review_architecture", ("repository_id",)),
    ("trace_api", ("repository_id", "endpoint")),
)

RESOURCES = (
    "repo://{repository_id}/analysis/endpoints",
    "repo://{repository_id}/architecture",
)


def test_only_analysis_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    shapes = []
    for tool in tools:
        description = (tool.description or "").strip().splitlines()[0]
        arguments = tuple((tool.inputSchema or {}).get("properties") or ())
        shapes.append((tool.name, description, arguments))
    assert tuple(sorted(shapes)) == TOOLS


def test_prompts_and_resources_are_registered():
    prompts = asyncio.run(mcp.list_prompts())
    shapes = tuple(sorted((item.name, tuple(arg.name for arg in item.arguments or [])) for item in prompts))
    assert shapes == PROMPTS
    resources = asyncio.run(mcp.list_resources())
    templates = asyncio.run(mcp.list_resource_templates())
    uris = sorted([str(item.uri) for item in resources] + [item.uriTemplate for item in templates])
    assert uris == list(RESOURCES)
