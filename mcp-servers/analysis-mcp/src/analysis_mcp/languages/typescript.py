"""TypeScript uses the same statement shapes as JavaScript, with its own grammar."""

from tree_sitter import Language, Parser
import tree_sitter_typescript

from analysis_mcp.languages.javascript import _visit

_TYPESCRIPT = Language(tree_sitter_typescript.language_typescript())
_TSX = Language(tree_sitter_typescript.language_tsx())


def collect(source: str, path: str) -> dict:
    """Parse one .ts or .tsx file."""
    language = _TSX if path.endswith(".tsx") else _TYPESCRIPT
    tree = Parser(language).parse(source.encode("utf-8"))
    found = {"functions": [], "classes": [], "imports": [], "endpoints": [], "calls": []}
    _visit(tree.root_node, path, [], found)
    return found
