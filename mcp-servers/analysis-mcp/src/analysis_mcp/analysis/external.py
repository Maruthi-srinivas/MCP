"""Outbound HTTP client calls. A missing URL literal is marked inferred."""

import ast

_CLIENTS = {"httpx", "requests", "aiohttp"}


def collect(tree: ast.AST, path: str) -> list[dict]:
    """Return httpx, requests, urllib.request, and aiohttp call sites."""
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        library = _client(node.func)
        if not library:
            continue
        url = _url(node)
        item = {"file": path, "line": node.lineno, "library": library, "inferred": url is None}
        if url is not None:
            item["url"] = url
        found.append(item)
    return found


def _client(func: ast.AST) -> str:
    names = _chain(func)
    if len(names) >= 2 and names[0] in _CLIENTS:
        return names[0]
    if names[:2] == ["urllib", "request"]:
        return "urllib.request"
    return ""


def _url(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    for keyword in call.keywords:
        if keyword.arg == "url" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _chain(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return _chain(node.value) + [node.attr]
    if isinstance(node, ast.Call):
        return _chain(node.func)
    return []
