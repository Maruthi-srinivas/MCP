"""Prompt text for a history question. git-mcp does not serve resources."""


def investigate_change(repository_id: str, path: str) -> str:
    """Investigate a recent change. Cite the commit SHA from tool results."""
    return (
        "Investigate a recent change. Cite file and line from tool results. Do not invent commits. "
        "Call get_file_history, get_commits, and get_diff. "
        f"repository_id is {repository_id}. The path is {path}."
    )


def register(mcp) -> None:
    mcp.prompt()(investigate_change)
