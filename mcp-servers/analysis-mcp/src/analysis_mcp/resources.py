"""JSON resources from the analysis artifact."""

import re

from investigator_shared.bounds import dump_resource, error_document
from investigator_shared.errors import ToolFailure

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.config import get_settings

_URI = re.compile(r"^repo://([^/]+)/(architecture|analysis/endpoints)$")


def read_architecture(repository_id: str) -> str:
    """Nodes and edges for this commit."""
    artifact, error = _artifact(repository_id)
    if error:
        return error
    payload = {
        "repository_id": repository_id,
        "commit_sha": artifact["commit_sha"],
        "analyzer_version": artifact["analyzer_version"],
        "nodes": artifact["nodes"],
        "edges": artifact["edges"],
        "entrypoints": artifact["entrypoints"],
        "external_services": artifact["external_services"],
        "truncated": artifact["truncated"],
    }
    return dump_resource(payload, get_settings().resource_max_chars)


def read_endpoints(repository_id: str) -> str:
    """HTTP routes already found for this commit."""
    artifact, error = _artifact(repository_id)
    if error:
        return error
    payload = {
        "repository_id": repository_id,
        "commit_sha": artifact["commit_sha"],
        "analyzer_version": artifact["analyzer_version"],
        "endpoints": artifact["endpoints"],
        "truncated": artifact["truncated"],
    }
    return dump_resource(payload, get_settings().resource_max_chars)


def read_uri(uri: str) -> str:
    match = _URI.match(uri)
    if match is None:
        return error_document("INVALID_PATH", "Unknown resource URI.", False)
    repository_id, kind = match.group(1), match.group(2)
    if kind == "architecture":
        return read_architecture(repository_id)
    return read_endpoints(repository_id)


def register(mcp) -> None:
    mcp.resource("repo://{repository_id}/architecture", mime_type="application/json")(read_architecture)
    mcp.resource("repo://{repository_id}/analysis/endpoints", mime_type="application/json")(read_endpoints)


def _artifact(repository_id: str) -> tuple[dict | None, str]:
    try:
        return ensure_artifact(repository_id), ""
    except ToolFailure as exc:
        return None, error_document(exc.code, exc.message, exc.retryable)
