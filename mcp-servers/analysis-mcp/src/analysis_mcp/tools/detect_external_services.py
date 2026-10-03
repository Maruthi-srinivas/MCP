"""HTTP client call sites."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.logging import observed_tool


@observed_tool
def detect_external_services(repository_id: str) -> dict:
    """Return httpx, requests, urllib.request, and aiohttp calls. A missing URL is inferred."""
    artifact = ensure_artifact(repository_id)
    return {
        "repository_id": repository_id,
        "services": artifact["external_services"],
        "truncated": artifact["truncated"],
    }
