"""Java classes, methods, imports, and calls recorded in the same file."""

import re
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_java

from analysis_mcp.languages.nodes import ident, line, text

_LANGUAGE = Language(tree_sitter_java.language())
_DEPENDENCY = re.compile(r"<dependency>(.*?)</dependency>", re.DOTALL)
_TAG = re.compile(r"<(groupId|artifactId)>\s*([^<]+?)\s*</\1>")


def collect(source: str, path: str) -> dict:
    """Parse one Java file."""
    tree = Parser(_LANGUAGE).parse(source.encode("utf-8"))
    found = {"functions": [], "classes": [], "imports": [], "endpoints": [], "calls": []}
    _visit(tree.root_node, path, [], found)
    return found


def collect_manifest(root: Path) -> list[dict]:
    """artifactId values from pom.xml dependency blocks. The path labels the row."""
    path = root / "pom.xml"
    if not path.is_file():
        return []
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = body.splitlines()
    rows = []
    for block in _DEPENDENCY.findall(body):
        tags = dict(_TAG.findall(block))
        artifact = tags.get("artifactId") or ""
        if not artifact:
            continue
        group = tags.get("groupId") or ""
        module = f"{group}:{artifact}" if group else artifact
        rows.append(
            {
                "path": "pom.xml",
                "line": _line(lines, artifact),
                "module": module,
                "names": [artifact],
                "level": 0,
            }
        )
    rows.sort(key=lambda item: (item["line"], item["module"]))
    return rows


def _visit(node, path: str, stack: list[str], found: dict) -> None:
    if node.type in {"class_declaration", "interface_declaration", "enum_declaration"}:
        name = ident(node.child_by_field_name("name"))
        if name:
            found["classes"].append({"name": name, "path": path, "line": line(node)})
        for child in node.children:
            _visit(child, path, stack, found)
        return
    if node.type in {"method_declaration", "constructor_declaration"}:
        name = ident(node.child_by_field_name("name"))
        if name:
            found["functions"].append({"name": name, "kind": "method", "path": path, "line": line(node)})
        stack.append(name or "anonymous")
        for child in node.children:
            _visit(child, path, stack, found)
        stack.pop()
        return
    if node.type == "import_declaration":
        module = _import_module(node)
        if module:
            found["imports"].append(
                {"path": path, "line": line(node), "module": module, "names": [module.split(".")[-1]], "level": 0}
            )
        return
    if node.type == "method_invocation" and stack:
        name = ident(node.child_by_field_name("name"))
        if name:
            found["calls"].append({"path": path, "line": line(node), "source": stack[-1], "name": name})
        for child in node.children:
            _visit(child, path, stack, found)
        return
    for child in node.children:
        _visit(child, path, stack, found)


def _import_module(node) -> str:
    for child in node.children:
        if child.type in {"scoped_identifier", "identifier"}:
            return text(child)
    raw = text(node).strip().removeprefix("import").removesuffix(";").strip()
    if raw.startswith("static "):
        raw = raw[len("static ") :]
    return raw


def _line(lines: list[str], artifact: str) -> int:
    needle = f">{artifact}<"
    for index, row in enumerate(lines, start=1):
        if needle in row:
            return index
    return 1
