"""Import edges that resolve to a project file, and call edges that match one function."""

import ast


def collect_calls(tree: ast.AST, path: str) -> list[dict]:
    """Record calls made inside a function. The callee name is the last attribute."""
    found: list[dict] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._enter(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._enter(node)

        def visit_Call(self, node: ast.Call) -> None:
            if self._stack:
                name = _callee(node.func)
                if name:
                    found.append({"path": path, "line": node.lineno, "source": self._stack[-1], "name": name})
            self.generic_visit(node)

        def _enter(self, node: ast.AST) -> None:
            self._stack.append(node.name)
            self.generic_visit(node)
            self._stack.pop()

    Visitor().visit(tree)
    return found


def build(functions: list[dict], imports: list[dict], calls: list[dict], files: set[str], limit: int) -> tuple[list[dict], list[dict], bool]:
    """Return nodes, edges, and whether the edge list was cut."""
    edges: list[dict] = []
    for item in imports:
        target = resolve_module(item["path"], item.get("module") or "", int(item.get("level") or 0), files)
        if target is None:
            continue
        edges.append(
            {
                "kind": "import",
                "inferred": False,
                "path": item["path"],
                "line": item["line"],
                "source": item["path"],
                "target": target,
                "target_path": target,
                "target_line": 1,
            }
        )
    by_name: dict[str, list[dict]] = {}
    for function in functions:
        by_name.setdefault(function["name"], []).append(function)
    for call in calls:
        matches = by_name.get(call["name"], [])
        if len(matches) != 1:
            continue
        target = matches[0]
        edges.append(
            {
                "kind": "call",
                "inferred": True,
                "path": call["path"],
                "line": call["line"],
                "source": call["source"],
                "target": target["name"],
                "target_path": target["path"],
                "target_line": target["line"],
            }
        )
    edges.sort(key=lambda item: (item["path"], item["line"], item["kind"], item["target"]))
    truncated = len(edges) > limit
    edges = edges[:limit]
    nodes = _nodes(functions, edges)
    return nodes, edges, truncated


def resolve_module(file_path: str, module: str, level: int, files: set[str]) -> str | None:
    """Map an import to a parsed project file, or return None for a third-party module."""
    parts = file_path.split("/")
    package = parts[:-1]
    if level:
        if level - 1 > len(package):
            return None
        base = package[: len(package) - (level - 1)]
        extra = [part for part in module.split(".") if part] if module else []
        candidate = base + extra
    elif module:
        candidate = [part for part in module.split(".") if part]
    else:
        return None
    if not candidate:
        return None
    relative = "/".join(candidate) + ".py"
    package_init = "/".join(candidate) + "/__init__.py"
    if relative in files:
        return relative
    if package_init in files:
        return package_init
    return None


def _callee(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _nodes(functions: list[dict], edges: list[dict]) -> list[dict]:
    nodes: dict[str, dict] = {}
    for function in functions:
        node_id = f"function:{function['path']}:{function['name']}:{function['line']}"
        nodes[node_id] = {
            "id": node_id,
            "kind": function["kind"],
            "name": function["name"],
            "path": function["path"],
            "line": function["line"],
        }
    for edge in edges:
        if edge["kind"] != "import":
            continue
        for file_path in (edge["path"], edge["target_path"]):
            node_id = f"file:{file_path}"
            nodes.setdefault(node_id, {"id": node_id, "kind": "file", "name": file_path, "path": file_path, "line": 1})
    return [nodes[key] for key in sorted(nodes)]
