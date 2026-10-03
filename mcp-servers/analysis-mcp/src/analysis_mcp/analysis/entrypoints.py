"""Files and assignments that look like process entrypoints."""

import ast


def collect(tree: ast.AST, path: str) -> list[dict]:
    """Return filename, __main__, and FastAPI/Flask assignment entrypoints."""
    found: list[dict] = []
    name = path.rsplit("/", 1)[-1]
    if name in {"main.py", "app.py"}:
        found.append({"path": path, "line": 1, "reason": "filename", "name": name})
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_main_guard(node):
            found.append({"path": path, "line": node.lineno, "reason": "main_guard", "name": "__main__"})
        assignment = _application(node, path)
        if assignment is not None:
            found.append(assignment)
    return found


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False
    compared = test.comparators[0] if test.comparators else None
    return isinstance(compared, ast.Constant) and compared.value == "__main__"


def _application(node: ast.AST, path: str) -> dict | None:
    value = None
    target = None
    if isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
        value = node.value
        target = node.targets[0]
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        value = node.value
        target = node.target
    if target is None or not isinstance(value, ast.Call):
        return None
    called = value.func.id if isinstance(value.func, ast.Name) else value.func.attr if isinstance(value.func, ast.Attribute) else ""
    if called not in {"FastAPI", "Flask"}:
        return None
    return {"path": path, "line": node.lineno, "reason": "application", "name": target.id}
