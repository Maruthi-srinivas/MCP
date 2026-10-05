import asyncio

from repository_mcp.server import mcp

# Name, first line of the description, argument names. A change here is a schema break.
TOOLS = (
    ("clone_repository", "Clone or refresh one public GitHub repository at a branch, tag, or commit SHA.", ("repository_url", "ref")),
    ("detect_project_type", "Detect Python and obvious frameworks such as FastAPI, Flask, and Django.", ("repository_id",)),
    ("detect_services", "Return top-level Python packages and modules that look like process entrypoints.", ("repository_id",)),
    ("find_dependencies", "Return name, version, and source file. A missing manifest is an empty list.", ("repository_id",)),
    ("find_references", "Return import sites and same-file name uses for an indexed symbol.", ("repository_id", "symbol")),
    ("find_symbol", "Return every indexed definition of symbol, with path, kind, and line range.", ("repository_id", "symbol")),
    ("get_repository_info", "Read owner, name, requested ref, and the commit SHA last fetched.", ("repository_id",)),
    ("list_directory", "List files and directories directly inside path, up to the configured cap.", ("repository_id", "path")),
    ("read_file", "Return a line window from a text file. Large files and long windows are bounded.", ("repository_id", "path", "start_line", "end_line")),
    ("search_code", "Find a text query and return file, line, and a short snippet for each hit.", ("repository_id", "query", "file_pattern")),
)

PROMPTS = (
    ("explain_repository", ("repository_id",)),
    ("explain_symbol", ("repository_id", "symbol")),
    ("onboard_developer", ("repository_id",)),
)

RESOURCES = (
    "repo://{repository_id}/dependencies",
    "repo://{repository_id}/file/{file_path}",
    "repo://{repository_id}/metadata",
    "repo://{repository_id}/structure",
)


def test_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    assert _tool_shapes(tools) == TOOLS


def test_prompts_and_resources_are_registered():
    prompts = asyncio.run(mcp.list_prompts())
    shapes = tuple(sorted((item.name, tuple(arg.name for arg in item.arguments or [])) for item in prompts))
    assert shapes == PROMPTS
    resources = asyncio.run(mcp.list_resources())
    templates = asyncio.run(mcp.list_resource_templates())
    uris = sorted([str(item.uri) for item in resources] + [item.uriTemplate for item in templates])
    assert uris == list(RESOURCES)


def _tool_shapes(tools) -> tuple:
    shapes = []
    for tool in tools:
        description = (tool.description or "").strip().splitlines()[0]
        arguments = tuple((tool.inputSchema or {}).get("properties") or ())
        shapes.append((tool.name, description, arguments))
    return tuple(sorted(shapes))
