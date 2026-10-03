"""Streamable HTTP MCP server plus a /health route.

Register tools here and nowhere else. Tool behavior lives in repository_mcp.tools.
"""

import contextlib
import logging

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from repository_mcp.config import get_settings
from repository_mcp.tools.clone_repository import clone_repository
from repository_mcp.tools.detect_project_type import detect_project_type
from repository_mcp.tools.detect_services import detect_services
from repository_mcp.tools.find_dependencies import find_dependencies
from repository_mcp.tools.find_references import find_references
from repository_mcp.tools.find_symbol import find_symbol
from repository_mcp.tools.get_repository_info import get_repository_info
from repository_mcp.tools.list_directory import list_directory
from repository_mcp.tools.read_file import read_file
from repository_mcp.tools.search_code import search_code

logging.basicConfig(level=logging.INFO, format="%(message)s")

mcp = FastMCP(
    "repository-mcp",
    instructions=(
        "Read-only GitHub repository inspection. "
        "Clone a public repository, then list directories, read bounded files, search code, "
        "and look up Python symbols, references, dependencies, and project structure."
    ),
    stateless_http=True,
    json_response=True,
)

mcp.tool()(clone_repository)
mcp.tool()(get_repository_info)
mcp.tool()(list_directory)
mcp.tool()(read_file)
mcp.tool()(search_code)
mcp.tool()(find_symbol)
mcp.tool()(find_references)
mcp.tool()(find_dependencies)
mcp.tool()(detect_project_type)
mcp.tool()(detect_services)


async def health(_: Request) -> JSONResponse:
    """Process health for Compose. This is not an MCP tool."""
    return JSONResponse({"status": "ok", "service": "repository-mcp"})


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
