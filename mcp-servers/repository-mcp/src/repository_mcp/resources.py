"""JSON resources for one repository commit. Tools stay the way to search."""

import re

from investigator_shared.bounds import dump_resource, error_document
from investigator_shared.errors import ToolFailure
from investigator_shared.secrets import redact

from repository_mcp.config import get_settings
from repository_mcp.intelligence.dependencies import find_manifest_dependencies
from repository_mcp.intelligence.index import ensure_index
from repository_mcp.workspace.paths import repository_root, resolve_inside
from repository_mcp.workspace.registry import get_repository

_FILE_URI = re.compile(r"^repo://([^/]+)/file/(.+)$")
_SIMPLE_URI = re.compile(r"^repo://([^/]+)/(metadata|structure|dependencies)$")


def read_metadata(repository_id: str) -> str:
    """Registry fields for this commit. The workspace path stays on the server."""
    try:
        record = get_repository(repository_id)
    except ToolFailure as exc:
        return error_document(exc.code, exc.message, exc.retryable)
    payload = {
        "repository_id": record["repository_id"],
        "url": record["url"],
        "owner": record["owner"],
        "name": record["name"],
        "ref": record["ref"],
        "resolved_commit": record["resolved_commit"],
        "status": record["status"],
        "truncated": False,
    }
    return dump_resource(payload, get_settings().resource_max_chars)


def read_structure(repository_id: str) -> str:
    """Symbols and Python files from the existing index."""
    try:
        index = ensure_index(repository_id)
    except ToolFailure as exc:
        return error_document(exc.code, exc.message, exc.retryable)
    payload = {
        "repository_id": repository_id,
        "commit_sha": index.get("commit_sha") or "",
        "analyzer_version": index.get("analyzer_version") or "",
        "symbols": index.get("symbols") or [],
        "python_files": index.get("python_files") or [],
        "warnings": index.get("warnings") or [],
        "truncated": bool(index.get("truncated")),
    }
    return dump_resource(payload, get_settings().resource_max_chars)


def read_dependencies(repository_id: str) -> str:
    """Manifest dependencies already discovered for this checkout."""
    try:
        index = ensure_index(repository_id)
        root = repository_root(repository_id)
    except ToolFailure as exc:
        return error_document(exc.code, exc.message, exc.retryable)
    dependencies, warnings = find_manifest_dependencies(root)
    payload = {
        "repository_id": repository_id,
        "commit_sha": index.get("commit_sha") or "",
        "dependencies": dependencies,
        "warnings": list(index.get("warnings") or []) + warnings,
        "truncated": bool(index.get("truncated")),
    }
    return dump_resource(payload, get_settings().resource_max_chars)


def read_file_resource(repository_id: str, file_path: str) -> str:
    """One file inside the checkout, with secrets removed and the line window capped."""
    settings = get_settings()
    try:
        root = repository_root(repository_id)
        path = resolve_inside(root, file_path)
        if path.is_dir() or not path.is_file():
            raise ToolFailure("FILE_NOT_FOUND", "File was not found.", False)
        if path.stat().st_size > settings.max_file_bytes:
            raise ToolFailure("FILE_TOO_LARGE", "File exceeds the configured size limit.", False)
        text = path.read_text(encoding="utf-8")
    except ToolFailure as exc:
        return error_document(exc.code, exc.message, exc.retryable)
    except UnicodeDecodeError:
        return error_document("FILE_TOO_LARGE", "File is not UTF-8 text.", False)
    redacted = redact(text)
    lines = redacted.splitlines()
    kept = lines[: settings.max_read_lines]
    truncated = len(lines) > len(kept)
    payload = {
        "repository_id": repository_id,
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "start_line": 1,
        "end_line": len(kept),
        "content": "\n".join(kept),
        "truncated": truncated,
    }
    return dump_resource(payload, settings.resource_max_chars)


def read_uri(uri: str) -> str:
    """Read a repo:// URI. The file path is everything after /file/."""
    file_match = _FILE_URI.match(uri)
    if file_match:
        return read_file_resource(file_match.group(1), file_match.group(2))
    simple = _SIMPLE_URI.match(uri)
    if simple is None:
        return error_document("INVALID_PATH", "Unknown resource URI.", False)
    repository_id, kind = simple.group(1), simple.group(2)
    if kind == "metadata":
        return read_metadata(repository_id)
    if kind == "structure":
        return read_structure(repository_id)
    return read_dependencies(repository_id)


def register(mcp) -> None:
    """Register the four repository resource templates."""
    mcp.resource("repo://{repository_id}/metadata", mime_type="application/json")(read_metadata)
    mcp.resource("repo://{repository_id}/structure", mime_type="application/json")(read_structure)
    mcp.resource("repo://{repository_id}/dependencies", mime_type="application/json")(read_dependencies)
    mcp.resource("repo://{repository_id}/file/{file_path}", mime_type="application/json")(read_file_resource)
    _install_uri_reader(mcp)


def _install_uri_reader(mcp) -> None:
    """Serve slash-containing file paths even when the template binds one segment."""
    original = mcp.read_resource

    async def read_resource(uri):
        text = str(uri)
        if not text.startswith("repo://"):
            return await original(uri)
        from mcp.server.fastmcp.resources.types import ReadResourceContents

        return [ReadResourceContents(content=read_uri(text), mime_type="application/json")]

    mcp.read_resource = read_resource
