"""Pick tools from the live list using words in the question."""

import json
import re

_METHOD = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b")
_PATH = re.compile(r"/[A-Za-z0-9][A-Za-z0-9_./-]*")
_FILENAME = re.compile(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9]+")
_DEF = re.compile(r"def\s+([A-Za-z_][A-Za-z0-9_]*)")


class ScriptedModel:
    """Stand-in for the chat model. It never calls OpenAI."""

    async def decide(self, question: str, repository_id: str, observations: list[dict], tool_names: list[str]) -> dict:
        names = set(tool_names)
        kind = _kind(question)
        if kind == "overview":
            return _overview(repository_id, observations, names)
        if kind == "missing":
            return _missing(question, repository_id, observations, names)
        if kind == "recent":
            return _recent(repository_id, observations, names)
        return _route(question, repository_id, observations, names)


_TRACE_TOOLS = ("search_code", "find_symbol", "read_file", "find_references", "detect_database_access")


def _kind(question: str) -> str:
    positions = [question.find(name) for name in _TRACE_TOOLS]
    if all(position >= 0 for position in positions) and positions == sorted(positions):
        return "route"
    lowered = question.lower()
    if "overview" in lowered or "what is this" in lowered:
        return "overview"
    if "missing" in lowered:
        return "missing"
    if "recent" in lowered or "commit" in lowered:
        return "recent"
    if _METHOD.search(question) and _PATH.search(question):
        return "route"
    return "overview"


def _overview(repository_id: str, observations: list[dict], names: set[str]) -> dict:
    if observations:
        return {"answer": "Overview is limited to the tool results.", "claims": []}
    calls = []
    for name in ("get_repository_info", "detect_project_type", "find_dependencies"):
        if name in names:
            calls.append({"name": name, "arguments": {"repository_id": repository_id}})
    return {"tool_calls": calls}


def _missing(question: str, repository_id: str, observations: list[dict], names: set[str]) -> dict:
    if observations or "read_file" not in names:
        return {"answer": "That file was not found, so this part is unknown.", "claims": []}
    match = _FILENAME.search(question)
    path = match.group(0) if match else "missing.txt"
    return {"tool_calls": [{"name": "read_file", "arguments": {"repository_id": repository_id, "path": path}}]}


def _recent(repository_id: str, observations: list[dict], names: set[str]) -> dict:
    if observations or "get_commits" not in names:
        return {"answer": "Recent history is limited to the commits the tool returned.", "claims": []}
    return {"tool_calls": [{"name": "get_commits", "arguments": {"repository_id": repository_id}}]}


def _route(question: str, repository_id: str, observations: list[dict], names: set[str]) -> dict:
    step = len(observations)
    path = _PATH.search(question)
    token = path.group(0) if path else ""
    symbol = _symbol(observations)
    found_file = _file(observations)
    if step == 0 and "search_code" in names:
        return {"tool_calls": [{"name": "search_code", "arguments": {"repository_id": repository_id, "query": token}}]}
    if step == 1 and "find_symbol" in names:
        return {"tool_calls": [{"name": "find_symbol", "arguments": {"repository_id": repository_id, "symbol": symbol}}]}
    if step == 2 and "read_file" in names:
        return {"tool_calls": [{"name": "read_file", "arguments": {"repository_id": repository_id, "path": found_file}}]}
    if step == 3 and "find_references" in names:
        return {"tool_calls": [{"name": "find_references", "arguments": {"repository_id": repository_id, "symbol": symbol}}]}
    if step == 4 and "detect_database_access" in names:
        return {"tool_calls": [{"name": "detect_database_access", "arguments": {"repository_id": repository_id}}]}
    return {"answer": "The route behavior is limited to the tool results. Anything else is unknown.", "claims": []}


def _symbol(observations: list[dict]) -> str:
    for item in observations:
        match = _DEF.search(item.get("text") or "")
        if match:
            return match.group(1)
    return "handler"


def _file(observations: list[dict]) -> str:
    for item in observations:
        try:
            payload = json.loads(item.get("text") or "{}")
        except json.JSONDecodeError:
            continue
        matches = payload.get("matches") or []
        if matches and matches[0].get("path"):
            return matches[0]["path"]
    return ""
