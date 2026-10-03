"""Coarse service list: top-level packages and obvious Python entrypoints."""

import ast
from pathlib import Path


def detect(index: dict, root: Path) -> list[dict]:
    """Return services with a path and a reason of package or entrypoint."""
    services: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for relative in index.get("python_files", []):
        path = root / relative
        if not path.is_file():
            continue
        if path.name in {"main.py", "app.py"} or _assigns_framework(path):
            _add(services, seen, path.stem, relative, "entrypoint")
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.name.startswith(".") or child.name in {"__pycache__", "venv", ".venv"}:
            continue
        if (child / "__init__.py").is_file():
            _add(services, seen, child.name, child.name, "package")
    services.sort(key=lambda item: (item["path"], item["reason"], item["name"]))
    return services


def _add(services: list[dict], seen: set[tuple[str, str]], name: str, path: str, reason: str) -> None:
    key = (path, reason)
    if key in seen:
        return
    seen.add(key)
    services.append({"name": name, "path": path, "reason": reason})


def _assigns_framework(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign):
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            value = node.value
        if isinstance(value, ast.Call) and _is_framework_call(value.func):
            return True
    return False


def _is_framework_call(func: ast.AST) -> bool:
    if isinstance(func, ast.Name) and func.id in {"FastAPI", "Flask"}:
        return True
    return isinstance(func, ast.Attribute) and func.attr in {"FastAPI", "Flask"}
