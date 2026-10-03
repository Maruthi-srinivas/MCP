"""Find name uses without following aliases.

A reference is either a load of the exact name in a file that defines it,
or an import line in another file that imports that exact name.
`import create_user as cu` counts the import line. Later uses of `cu` do not.
"""

import ast
from pathlib import Path

from repository_mcp.workspace.paths import resolve_inside


def collect_references(index: dict, root: Path, symbol: str, limit: int) -> tuple[list[dict], bool]:
    """Return up to limit references and whether more were dropped."""
    definitions = [item for item in index["symbols"] if item["name"] == symbol]
    defining_paths = {item["path"] for item in definitions}
    found: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for item in index["imports"]:
        if symbol not in item["names"]:
            continue
        _add(found, seen, root, item["path"], item["line"])

    for relative in sorted(defining_paths):
        file_path = resolve_inside(root, relative)
        if not file_path.is_file():
            continue
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        definition_lines = {item["start_line"] for item in definitions if item["path"] == relative}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != symbol:
                continue
            if not isinstance(node.ctx, ast.Load):
                continue
            if node.lineno in definition_lines:
                continue
            _add(found, seen, root, relative, node.lineno)

    found.sort(key=lambda item: (item["path"], item["line"]))
    truncated = len(found) > limit
    return found[:limit], truncated


def _add(found: list[dict], seen: set[tuple[str, int]], root: Path, relative: str, line: int) -> None:
    key = (relative, line)
    if key in seen:
        return
    seen.add(key)
    found.append({"path": relative, "line": line, "snippet": _snippet(root, relative, line)})


def _snippet(root: Path, relative: str, line: int) -> str:
    file_path = resolve_inside(root, relative)
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    if line < 1 or line > len(lines):
        return ""
    text = lines[line - 1].strip()
    return text[:200]
