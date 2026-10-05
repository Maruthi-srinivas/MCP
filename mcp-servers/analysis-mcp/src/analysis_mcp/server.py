"""Python structure MCP. This server does not clone and does not call a model."""

import contextlib
import logging

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from investigator_shared.secrets import install_redacting_logs

from analysis_mcp.config import get_settings
from analysis_mcp.prompts import register as register_prompts
from analysis_mcp.resources import register as register_resources
from analysis_mcp.tools.analyze_code import analyze_code
from analysis_mcp.tools.build_dependency_graph import build_dependency_graph
from analysis_mcp.tools.detect_api_endpoints import detect_api_endpoints
from analysis_mcp.tools.detect_database_access import detect_database_access
from analysis_mcp.tools.detect_entrypoints import detect_entrypoints
from analysis_mcp.tools.detect_external_services import detect_external_services
from analysis_mcp.tools.find_classes import find_classes
from analysis_mcp.tools.find_functions import find_functions
from analysis_mcp.tools.find_imports import find_imports

logging.basicConfig(level=logging.INFO, format="%(message)s")
install_redacting_logs()


def _transport_security() -> TransportSecuritySettings:
    """Allow Compose service names. Localhost stays allowed for the health check path."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "repository-mcp:*", "git-mcp:*", "analysis-mcp:*"],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://repository-mcp:*",
            "http://git-mcp:*",
            "http://analysis-mcp:*",
        ],
    )


mcp = FastMCP(
    "analysis-mcp",
    instructions=(
        "Python structure for a repository that Repository MCP already cloned. "
        "File contents stay on the repository server. History stays on the git server. "
        "This server does not summarize results with a model."
    ),
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    transport_security=_transport_security(),
)

mcp.tool()(analyze_code)
mcp.tool()(find_functions)
mcp.tool()(find_classes)
mcp.tool()(find_imports)
mcp.tool()(build_dependency_graph)
mcp.tool()(detect_entrypoints)
mcp.tool()(detect_api_endpoints)
mcp.tool()(detect_database_access)
mcp.tool()(detect_external_services)

register_resources(mcp)
register_prompts(mcp)


async def health(_: Request) -> JSONResponse:
    """Process health for Compose. This is not an MCP tool."""
    return JSONResponse({"status": "ok", "service": "analysis-mcp"})


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
