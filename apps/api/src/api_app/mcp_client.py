"""Call MCP over HTTP. This process does not import the MCP servers."""

import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from api_app.config import get_settings

_TOOLS = {
    "clone_repository": "repository",
    "search_code": "repository",
    "read_file": "repository",
    "analyze_code": "analysis",
}


def _servers() -> list[tuple[str, str]]:
    settings = get_settings()
    return [
        ("repository-mcp", settings.repository_mcp_url),
        ("git-mcp", settings.git_mcp_url),
        ("analysis-mcp", settings.analysis_mcp_url),
    ]


def _url(server: str) -> str:
    settings = get_settings()
    if server == "analysis":
        return settings.analysis_mcp_url
    return settings.repository_mcp_url


async def call_tool(name: str, arguments: dict) -> dict:
    result = await _call(_url(_TOOLS[name]), name, arguments)
    return result


async def list_prompts() -> list[dict]:
    """Name, server, and argument names from each MCP server."""
    found: list[dict] = []
    for server, url in _servers():
        for prompt in await _list_prompts(url):
            arguments = []
            for item in getattr(prompt, "arguments", None) or []:
                arguments.append(
                    {
                        "name": getattr(item, "name", "") or "",
                        "required": bool(getattr(item, "required", False)),
                    }
                )
            found.append({"name": prompt.name, "server": server, "arguments": arguments})
    found.sort(key=lambda item: (item["server"], item["name"]))
    return found


async def read_json(uri: str) -> dict:
    settings = get_settings()
    url = settings.repository_mcp_url
    if "/architecture" in uri or "/analysis/" in uri:
        url = settings.analysis_mcp_url
    text = await _read(url, uri)
    return json.loads(text)


async def _call(url: str, name: str, arguments: dict) -> dict:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text[:4000]}
        if isinstance(parsed, dict):
            return parsed
    return {}


async def _list_prompts(url: str) -> list:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_prompts()
    return list(listed.prompts)


async def _read(url: str, uri: str) -> str:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(uri)
    parts: list[str] = []
    for block in result.contents:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)
