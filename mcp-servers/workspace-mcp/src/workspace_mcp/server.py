"""Write tools for one cloned workspace. They stay unregistered until WRITE_ENABLED=1."""

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

from workspace_mcp.config import get_settings, write_enabled
from workspace_mcp.metrics import snapshot as metrics_snapshot
from workspace_mcp.tools.apply_patch import apply_patch
from workspace_mcp.tools.preview_patch import preview_patch
from workspace_mcp.tools.propose_patch import propose_patch

logging.basicConfig(level=logging.INFO, format="%(message)s")
install_redacting_logs()


def _transport_security() -> TransportSecuritySettings:
    """Allow the Compose host name. A missing name returns HTTP 421."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "repository-mcp:*",
            "git-mcp:*",
            "analysis-mcp:*",
            "workspace-mcp:*",
            "agent:*",
            "api:*",
        ],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://repository-mcp:*",
            "http://git-mcp:*",
            "http://analysis-mcp:*",
            "http://workspace-mcp:*",
            "http://agent:*",
            "http://api:*",
        ],
    )


def register_tools(server: FastMCP) -> None:
    """Add the write tools only when the flag is on."""
    if not write_enabled():
        return
    server.tool()(propose_patch)
    server.tool()(preview_patch)
    server.tool()(apply_patch)


mcp = FastMCP(
    "workspace-mcp",
    instructions=(
        "Propose a small unified diff. The workspace file changes only after "
        "the repository owner approves that proposal."
    ),
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    transport_security=_transport_security(),
)
register_tools(mcp)


async def health(_: Request) -> JSONResponse:
    """Process health for Compose. This is not an MCP tool."""
    return JSONResponse({"status": "ok", "service": "workspace-mcp"})


async def metrics(_: Request) -> JSONResponse:
    """Counters and histograms for this process. A restart clears them."""
    return JSONResponse(metrics_snapshot())


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/metrics", endpoint=metrics, methods=["GET"]),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
