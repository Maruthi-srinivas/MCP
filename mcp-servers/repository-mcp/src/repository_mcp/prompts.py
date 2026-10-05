"""Prompt text for repository workflows. The text names tools and does not embed source."""


def explain_repository(repository_id: str) -> str:
    """Explain what this repository is. Cite file and line from tool results."""
    return (
        "Explain the repository. Cite file and line from tool results. Do not invent files. "
        "Call get_repository_info, detect_project_type, and find_dependencies. "
        f"repository_id is {repository_id}."
    )


def onboard_developer(repository_id: str) -> str:
    """Point a new reader at the layout. Cite file and line from tool results."""
    return (
        "Onboard a developer. Cite file and line from tool results. Do not invent files. "
        "Call list_directory, detect_services, find_dependencies, and read_file. "
        f"repository_id is {repository_id}."
    )


def explain_symbol(repository_id: str, symbol: str) -> str:
    """Explain one symbol. Cite file and line from tool results."""
    return (
        "Explain one symbol. Cite file and line from tool results. Do not invent files. "
        "Call search_symbols, find_symbol, find_references, and read_file. "
        f"repository_id is {repository_id}. The symbol is {symbol}."
    )


def register(mcp) -> None:
    mcp.prompt()(explain_repository)
    mcp.prompt()(onboard_developer)
    mcp.prompt()(explain_symbol)
