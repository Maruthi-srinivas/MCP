"""Prompt catalog. The names come from the MCP servers."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api_app.mcp_client import list_prompts

router = APIRouter()


@router.get("/prompts")
async def prompts():
    try:
        catalog = await list_prompts()
    except Exception:
        return JSONResponse(
            {"error": {"code": "INTERNAL_ERROR", "message": "Prompt catalog is unavailable.", "retryable": True}},
            status_code=503,
        )
    return {"prompts": catalog}
