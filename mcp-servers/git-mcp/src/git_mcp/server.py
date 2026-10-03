"""Read-only Git MCP. This server does not clone or update refs."""

import contextlib
import logging

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from git_mcp.config import get_settings
from git_mcp.prompts import register as register_prompts
from git_mcp.tools.compare_branches import compare_branches
from git_mcp.tools.find_introduced_change import find_introduced_change
from git_mcp.tools.get_branches import get_branches
from git_mcp.tools.get_commit import get_commit
from git_mcp.tools.get_commits import get_commits
from git_mcp.tools.get_diff import get_diff
from git_mcp.tools.get_file_history import get_file_history
from git_mcp.tools.get_git_status import get_git_status

logging.basicConfig(level=logging.INFO, format="%(message)s")

mcp = FastMCP(
    "git-mcp",
    instructions=(
        "Read-only git history for a repository that Repository MCP already cloned. "
        "File contents stay on the repository server."
    ),
    stateless_http=True,
    json_response=True,
)

mcp.tool()(get_git_status)
mcp.tool()(get_branches)
mcp.tool()(get_commits)
mcp.tool()(get_commit)
mcp.tool()(get_diff)
mcp.tool()(get_file_history)
mcp.tool()(compare_branches)
mcp.tool()(find_introduced_change)

register_prompts(mcp)


async def health(_: Request) -> JSONResponse:
    """Process health for Compose. This is not an MCP tool."""
    return JSONResponse({"status": "ok", "service": "git-mcp"})


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", endpoint=health, methods=["GET"]),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
