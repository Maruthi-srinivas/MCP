"""Database hints. An import or a call site is not proof that a query ran."""

import ast

_MODULES = {"sqlalchemy", "sqlite3", "psycopg", "psycopg2", "asyncpg"}


def collect(tree: ast.AST, path: str) -> list[dict]:
    """Return import and call hints in this file."""
    found: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                library = _library(alias.name)
                if library:
                    found.append({"file": path, "line": node.lineno, "library": library, "kind": "import"})
        elif isinstance(node, ast.ImportFrom) and node.module:
            library = _library(node.module)
            if library:
                found.append({"file": path, "line": node.lineno, "library": library, "kind": "import"})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"execute", "query"} and _uses_cursor_or_session(node.func.value):
                found.append({"file": path, "line": node.lineno, "library": "sql", "kind": "call"})
    return found


def _library(module: str) -> str:
    if module == "django.db" or module.startswith("django.db."):
        return "django.db"
    root = module.split(".", 1)[0]
    if root in _MODULES:
        return root
    return ""


def _uses_cursor_or_session(node: ast.AST) -> bool:
    names: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.Name):
            names.append(current.id)
            break
        if isinstance(current, ast.Attribute):
            names.append(current.attr)
            current = current.value
            continue
        if isinstance(current, ast.Call):
            current = current.func
            continue
        break
    return "cursor" in names or "session" in names
