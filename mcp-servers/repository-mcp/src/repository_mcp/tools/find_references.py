"""Find AST uses of a Python symbol. Aliases are not followed."""

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.intelligence.index import ensure_index, require_python
from repository_mcp.intelligence.references import collect_references
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root


@observed_tool
def find_references(repository_id: str, symbol: str) -> dict:
    """Return import sites and same-file name uses for an indexed symbol."""
    if not symbol or not symbol.strip():
        raise ToolFailure("SYMBOL_NOT_FOUND", "Symbol name must not be empty.", False)
    index = ensure_index(repository_id)
    require_python(index)
    if not any(item["name"] == symbol for item in index["symbols"]):
        raise ToolFailure("SYMBOL_NOT_FOUND", f"{symbol} was not found.", False)
    references, truncated = collect_references(
        index,
        repository_root(repository_id),
        symbol,
        get_settings().max_references,
    )
    return {
        "repository_id": repository_id,
        "symbol": symbol,
        "references": references,
        "warnings": index["warnings"],
        "truncated": truncated or bool(index.get("truncated")),
    }
