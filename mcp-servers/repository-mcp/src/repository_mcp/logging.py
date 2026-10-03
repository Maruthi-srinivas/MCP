"""One JSON log line per tool call. Arguments and tokens are not logged."""

import functools
import logging
import time
import uuid
from collections.abc import Callable

from repository_mcp.errors import ToolFailure, error_body

logger = logging.getLogger("repository_mcp")


def _result_items(result: dict) -> int:
    if "error" in result:
        return 0
    for key in ("matches", "definitions", "references", "dependencies", "services"):
        if key in result:
            return len(result[key])
    if "files" in result or "directories" in result:
        return len(result.get("files", [])) + len(result.get("directories", []))
    return 1


def log_tool_call(
    *,
    request_id: str,
    tool: str,
    duration_ms: int,
    status: str,
    result_items: int,
    error_code: str | None = None,
) -> None:
    """Emit the structured line operators read with docker compose logs."""
    payload = {
        "request_id": request_id,
        "mcp_server": "repository-mcp",
        "tool": tool,
        "duration_ms": duration_ms,
        "status": status,
        "result_items": result_items,
    }
    if error_code:
        payload["error_code"] = error_code
    logger.info("%s", payload)


def observed_tool(fn: Callable) -> Callable:
    """Log the call and turn ToolFailure into the public error object."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        request_id = "req_" + uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except ToolFailure as failure:
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_tool_call(
                request_id=request_id,
                tool=fn.__name__,
                duration_ms=duration_ms,
                status="error",
                result_items=0,
                error_code=failure.code,
            )
            return error_body(failure, request_id)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_tool_call(
                request_id=request_id,
                tool=fn.__name__,
                duration_ms=duration_ms,
                status="error",
                result_items=0,
                error_code="INTERNAL_ERROR",
            )
            logger.exception("tool %s failed", fn.__name__)
            return error_body(
                ToolFailure("INTERNAL_ERROR", "Unexpected server error.", False),
                request_id,
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_tool_call(
            request_id=request_id,
            tool=fn.__name__,
            duration_ms=duration_ms,
            status="success",
            result_items=_result_items(result),
        )
        return result

    return wrapper
