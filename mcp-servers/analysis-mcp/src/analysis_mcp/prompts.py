"""Prompt text for analysis workflows. The text names tools and does not embed source."""


def review_architecture(repository_id: str) -> str:
    """Review the component graph. Cite file and line from tool results."""
    return (
        "Review the architecture. Cite file and line from tool results. Do not invent files. "
        "Call build_dependency_graph, detect_api_endpoints, and detect_entrypoints. "
        f"repository_id is {repository_id}."
    )


def trace_api(repository_id: str, endpoint: str) -> str:
    """Trace one HTTP endpoint. Cite file and line from tool results."""
    return (
        "Trace one HTTP endpoint. Cite file and line from tool results. Do not invent files. "
        "Call these tools in order: search_symbols, search_code, find_symbol, read_file, find_references, detect_database_access. "
        f"repository_id is {repository_id}. The endpoint path is {endpoint}."
    )


def register(mcp) -> None:
    mcp.prompt()(review_architecture)
    mcp.prompt()(trace_api)
