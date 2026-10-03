"""Locate Python function, method, and class definitions."""

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.intelligence.index import ensure_index, require_python
from repository_mcp.logging import observed_tool


@observed_tool
def find_symbol(repository_id: str, symbol: str) -> dict:
    """Return every indexed definition of symbol, with path, kind, and line range."""
    if not symbol or not symbol.strip():
        raise ToolFailure("SYMBOL_NOT_FOUND", "Symbol name must not be empty.", False)
    index = ensure_index(repository_id)
    require_python(index)
    definitions = [item for item in index["symbols"] if item["name"] == symbol]
    if not definitions:
        raise ToolFailure("SYMBOL_NOT_FOUND", f"{symbol} was not found.", False)
    limit = get_settings().max_symbols
    truncated = len(definitions) > limit or bool(index.get("truncated"))
    return {
        "repository_id": repository_id,
        "symbol": symbol,
        "definitions": definitions[:limit],
        "warnings": index["warnings"],
        "truncated": truncated,
    }
