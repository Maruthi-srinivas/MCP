"""The only module that calls MCP over HTTP."""

import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agent_app.config import Settings


class HttpMcpHub:
    """List and call tools on the three Compose servers. One session per call."""

    def __init__(self, settings: Settings) -> None:
        self._servers = {
            "repository-mcp": settings.repository_mcp_url,
            "git-mcp": settings.git_mcp_url,
            "analysis-mcp": settings.analysis_mcp_url,
        }
        self._owners: dict[str, str] = {}
        self._prompt_owners: dict[str, str] = {}

    async def list_tools(self) -> list[dict]:
        found: list[dict] = []
        for server, url in self._servers.items():
            for name in await _list_one(url):
                self._owners.setdefault(name, server)
                found.append({"name": name, "server": server})
        return found

    async def call_tool(self, name: str, arguments: dict) -> dict:
        if not self._owners:
            await self.list_tools()
        server = self._owners.get(name)
        if server is None:
            return {"error": {"code": "INTERNAL_ERROR", "message": f"Unknown tool {name}.", "retryable": False}}
        return await _call_one(self._servers[server], name, arguments)

    def server_for(self, name: str) -> str:
        return self._owners.get(name, "")

    async def list_prompts(self) -> list[dict]:
        found: list[dict] = []
        for server, url in self._servers.items():
            for name in await _list_prompts(url):
                self._prompt_owners.setdefault(name, server)
                found.append({"name": name, "server": server})
        return found

    async def get_prompt(self, name: str, arguments: dict) -> str | None:
        if name not in self._prompt_owners:
            await self.list_prompts()
        server = self._prompt_owners.get(name)
        if server is None:
            return None
        return await _get_prompt(self._servers[server], name, arguments)


async def _list_one(url: str) -> list[str]:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
    return [tool.name for tool in listed.tools]


async def _list_prompts(url: str) -> list[str]:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_prompts()
    return [prompt.name for prompt in listed.prompts]


async def _get_prompt(url: str, name: str, arguments: dict) -> str:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.get_prompt(name, {key: str(value) for key, value in arguments.items()})
    parts: list[str] = []
    for message in result.messages:
        content = message.content
        blocks = content if isinstance(content, list) else [content]
        for block in blocks:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts)


async def _call_one(url: str, name: str, arguments: dict) -> dict:
    async with streamablehttp_client(url) as (read, write, _session):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
    return _payload(result)


def _payload(result) -> dict:
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
    if getattr(result, "isError", False):
        return {"error": {"code": "INTERNAL_ERROR", "message": "Tool call failed.", "retryable": False}}
    return {}
