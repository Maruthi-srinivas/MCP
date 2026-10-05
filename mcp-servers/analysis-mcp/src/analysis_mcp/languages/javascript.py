"""JavaScript functions, classes, imports, Express routes, and same-file calls."""

import json
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_javascript

from analysis_mcp.languages.nodes import ident, line, string_value, text

_LANGUAGE = Language(tree_sitter_javascript.language())
_METHODS = {"get", "post", "put", "delete"}
_FUNCTION_NODES = {"function_declaration", "function", "function_expression", "arrow_function", "method_definition"}


def parser() -> Parser:
    """One parser for the JavaScript grammar."""
    return Parser(_LANGUAGE)


def collect(source: str, path: str) -> dict:
    """Parse one JavaScript file into the same shapes the Python walk produces."""
    tree = parser().parse(source.encode("utf-8"))
    found = {"functions": [], "classes": [], "imports": [], "endpoints": [], "calls": []}
    _visit(tree.root_node, path, [], found)
    return found


def collect_manifest(root: Path) -> list[dict]:
    """Dependency names from package.json. The path labels the row as a manifest."""
    path = root / "package.json"
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names: list[str] = []
    for key in ("dependencies", "devDependencies"):
        block = document.get(key) or {}
        if isinstance(block, dict):
            names.extend(str(name) for name in block)
    body = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for name in sorted(set(names)):
        rows.append(
            {
                "path": "package.json",
                "line": _manifest_line(body, name),
                "module": name,
                "names": [name],
                "level": 0,
            }
        )
    return rows


def _visit(node, path: str, stack: list[str], found: dict) -> None:
    if node.type == "import_statement":
        found["imports"].extend(_import(node, path))
        return
    if node.type == "class_declaration":
        name = ident(node.child_by_field_name("name"))
        if name:
            found["classes"].append({"name": name, "path": path, "line": line(node)})
        for child in node.children:
            _visit(child, path, stack, found)
        return
    if node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        name = ident(node.child_by_field_name("name"))
        if name and value is not None and value.type in _FUNCTION_NODES:
            found["functions"].append({"name": name, "kind": "function", "path": path, "line": line(node)})
            stack.append(name)
            _visit(value, path, stack, found)
            stack.pop()
            return
    if node.type in _FUNCTION_NODES:
        name = _function_name(node)
        if name:
            kind = "method" if node.type == "method_definition" else "function"
            found["functions"].append({"name": name, "kind": kind, "path": path, "line": line(node)})
        stack.append(name or "anonymous")
        for child in node.children:
            _visit(child, path, stack, found)
        stack.pop()
        return
    if node.type == "call_expression":
        route = _express(node, path)
        if route is not None:
            found["endpoints"].append(route)
        required = _require(node, path)
        if required is not None:
            found["imports"].append(required)
        callee = _callee(node)
        if stack and callee and callee != "require":
            found["calls"].append({"path": path, "line": line(node), "source": stack[-1], "name": callee})
        for child in node.children:
            _visit(child, path, stack, found)
        return
    for child in node.children:
        _visit(child, path, stack, found)


def _function_name(node) -> str:
    name = node.child_by_field_name("name")
    return ident(name)


def _callee(node) -> str:
    func = node.child_by_field_name("function")
    if func is None:
        return ""
    if func.type == "identifier":
        return text(func)
    if func.type == "member_expression":
        prop = func.child_by_field_name("property")
        return ident(prop)
    return ""


def _express(node, path: str) -> dict | None:
    func = node.child_by_field_name("function")
    if func is None or func.type != "member_expression":
        return None
    prop = ident(func.child_by_field_name("property"))
    if prop not in _METHODS:
        return None
    receiver = func.child_by_field_name("object")
    if receiver is None or receiver.type != "identifier" or text(receiver) not in {"app", "router"}:
        return None
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return None
    route = ""
    for child in arguments.children:
        if child.type == "string":
            route = string_value(child)
            break
    if not route:
        return None
    return {"framework": "express", "method": prop.upper(), "path": route, "file": path, "line": line(node)}


def _require(node, path: str) -> dict | None:
    if _callee(node) != "require":
        return None
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return None
    for child in arguments.children:
        if child.type == "string":
            module = string_value(child)
            return {"path": path, "line": line(node), "module": module, "names": [module], "level": 0}
    return None


def _import(node, path: str) -> list[dict]:
    module = ""
    names: list[str] = []
    for child in node.children:
        if child.type == "string":
            module = string_value(child)
        elif child.type == "identifier":
            names.append(text(child))
        elif child.type == "import_clause":
            names.extend(_clause_names(child))
    if not module and not names:
        return []
    return [{"path": path, "line": line(node), "module": module, "names": names or [module], "level": 0}]


def _clause_names(node) -> list[str]:
    names = []
    for child in node.children:
        if child.type in {"identifier", "namespace_import"}:
            names.append(text(child).replace("* as ", "").strip())
        elif child.type == "named_imports":
            for spec in child.children:
                if spec.type == "import_specifier":
                    name = spec.child_by_field_name("name") or spec.child_by_field_name("alias")
                    if name is not None:
                        names.append(text(name))
    return [name for name in names if name and name not in {"{", "}", ","}]


def _manifest_line(lines: list[str], name: str) -> int:
    needle = f'"{name}"'
    for index, row in enumerate(lines, start=1):
        if needle in row:
            return index
    return 1
