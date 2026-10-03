"""In-process MCP stub. Contract tests never open a network connection."""

import asyncio

_TOOLS = {
    "clone_repository": "repository-mcp",
    "get_repository_info": "repository-mcp",
    "search_code": "repository-mcp",
    "find_symbol": "repository-mcp",
    "read_file": "repository-mcp",
    "find_references": "repository-mcp",
    "find_dependencies": "repository-mcp",
    "detect_project_type": "repository-mcp",
    "get_commits": "git-mcp",
    "detect_database_access": "analysis-mcp",
}

COMMIT = "a" * 40


class FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.queued: dict[str, list[dict]] = {}
        self._owners = dict(_TOOLS)
        self.inflight = 0
        self.max_inflight = 0

    async def list_tools(self) -> list[dict]:
        return [{"name": name, "server": server} for name, server in _TOOLS.items()]

    def server_for(self, name: str) -> str:
        return self._owners.get(name, "")

    async def list_prompts(self) -> list[dict]:
        return [{"name": "trace_api", "server": "analysis-mcp"}]

    async def get_prompt(self, name: str, arguments: dict) -> str | None:
        if name != "trace_api":
            return None
        endpoint = str((arguments or {}).get("endpoint") or "")
        return (
            "Trace one HTTP endpoint. Cite file and line from tool results. "
            "Call these tools in order: search_code, find_symbol, read_file, "
            "find_references, detect_database_access. "
            f"The endpoint path is {endpoint}."
        )

    async def call_tool(self, name: str, arguments: dict) -> dict:
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        await asyncio.sleep(0.05)
        self.calls.append((name, arguments))
        self.inflight -= 1
        queued = self.queued.get(name) or []
        if queued:
            return queued.pop(0)
        return _result(name, arguments)


def _result(name: str, arguments: dict) -> dict:
    repository_id = arguments.get("repository_id") or "repo_from_clone"
    if name == "clone_repository":
        return {"repository_id": "repo_from_clone", "resolved_commit": COMMIT, "status": "ready"}
    if name == "read_file" and "missing" in str(arguments.get("path") or ""):
        return {"error": {"code": "FILE_NOT_FOUND", "message": "File was not found.", "retryable": False}}
    if name == "search_code":
        return {
            "repository_id": repository_id,
            "resolved_commit": COMMIT,
            "matches": [{"path": "app/main.py", "line": 8, "snippet": "def post_users():"}],
        }
    if name == "find_symbol":
        return {
            "repository_id": repository_id,
            "definitions": [{"name": arguments.get("symbol") or "post_users", "path": "app/main.py", "start_line": 8, "end_line": 11}],
        }
    if name == "read_file":
        return {
            "repository_id": repository_id,
            "path": arguments.get("path") or "app/main.py",
            "start_line": 8,
            "end_line": 11,
            "content": "def post_users():\n    return create_user()",
        }
    if name == "find_references":
        return {"repository_id": repository_id, "references": [{"path": "app/main.py", "line": 10}]}
    if name == "detect_database_access":
        return {"hints": [{"file": "app/users/service.py", "line": 4, "library": "sqlite3"}]}
    if name == "get_repository_info":
        return {"repository_id": repository_id, "resolved_commit": COMMIT, "status": "ready"}
    if name == "get_commits":
        return {"commits": [{"sha": COMMIT, "subject": "change"}]}
    return {"repository_id": repository_id, "resolved_commit": COMMIT}
