"""HTTP routes taken from decorators and Django url patterns. The path is a string literal."""

import ast

_METHOD_ATTRS = {"get", "post", "put", "patch", "delete"}
_ROUTE_ATTRS = _METHOD_ATTRS | {"route", "api_route"}


def collect(tree: ast.AST, path: str) -> list[dict]:
    """Return endpoints declared in this file."""
    apps = _applications(tree)
    found: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.extend(_decorated(node, path, apps))
        elif path.endswith("urls.py") and isinstance(node, ast.Call):
            django = _django_pattern(node, path)
            if django is not None:
                found.append(django)
    return found


def _applications(tree: ast.AST) -> dict[str, str]:
    """Map a variable name to fastapi or flask when the file constructs that app."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        value = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Call):
            continue
        framework = _framework_name(value.func)
        if framework is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                found[target.id] = framework
    return found


def _framework_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name) and func.id in {"FastAPI", "Flask"}:
        return "fastapi" if func.id == "FastAPI" else "flask"
    if isinstance(func, ast.Attribute) and func.attr in {"FastAPI", "Flask"}:
        return "fastapi" if func.attr == "FastAPI" else "flask"
    return None


def _decorated(node: ast.AST, path: str, apps: dict[str, str]) -> list[dict]:
    found: list[dict] = []
    for decorator in node.decorator_list:
        api_view = _api_view(decorator, path, node.lineno)
        if api_view is not None:
            found.append(api_view)
            continue
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        attr = decorator.func.attr
        if attr not in _ROUTE_ATTRS:
            continue
        route = _literal(decorator.args[0]) if decorator.args else None
        if route is None:
            continue
        receiver = decorator.func.value
        framework = apps.get(receiver.id) if isinstance(receiver, ast.Name) else None
        if framework is None:
            framework = "flask" if attr == "route" else "fastapi"
        method = attr.upper() if attr in _METHOD_ATTRS else _methods_keyword(decorator) or "GET"
        found.append(
            {"framework": framework, "method": method, "path": route, "file": path, "line": decorator.lineno}
        )
    return found


def _api_view(decorator: ast.AST, path: str, line: int) -> dict | None:
    """Django REST framework marks the view here. The URL path stays in urls.py."""
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    if name != "api_view":
        return None
    methods = []
    if isinstance(decorator, ast.Call) and decorator.args and isinstance(decorator.args[0], (ast.List, ast.Tuple)):
        methods = [item.value for item in decorator.args[0].elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    return {
        "framework": "django",
        "method": ",".join(methods),
        "path": "",
        "file": path,
        "line": line,
    }


def _django_pattern(node: ast.Call, path: str) -> dict | None:
    name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
    if name not in {"path", "re_path"} or not node.args:
        return None
    route = _literal(node.args[0])
    if route is None:
        return None
    return {"framework": "django", "method": "", "path": route, "file": path, "line": node.lineno}


def _methods_keyword(call: ast.Call) -> str:
    for keyword in call.keywords:
        if keyword.arg != "methods" or not isinstance(keyword.value, (ast.List, ast.Tuple)):
            continue
        methods = [item.value for item in keyword.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if methods:
            return ",".join(methods)
    return ""


def _literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
