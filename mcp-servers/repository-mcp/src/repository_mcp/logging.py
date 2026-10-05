"""One key=value log line per tool call. Arguments and tokens are not logged."""

import functools
import inspect
import logging
import time
import uuid
from collections.abc import Callable

from investigator_shared.secrets import log_event

from repository_mcp.errors import ToolFailure, error_body
from repository_mcp.metrics import record

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
    repository_id: str = "",
) -> None:
    """Emit the structured line operators read with docker compose logs."""
    del result_items
    record(tool, duration_ms, status)
    if tool == "clone_repository":
        record("clone", duration_ms, status)
    log_event(
        "tool_call",
        duration_ms=duration_ms,
        status=status,
        request_id=request_id,
        repository_id=repository_id,
        tool=tool,
        error_code=error_code,
    )


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
                repository_id=_repository_id(fn, args, kwargs, None),
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
                repository_id=_repository_id(fn, args, kwargs, None),
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
            repository_id=_repository_id(fn, args, kwargs, result),
        )
        return result

    return wrapper


def _repository_id(fn: Callable, args: tuple, kwargs: dict, result: dict | None) -> str:
    if kwargs.get("repository_id"):
        return str(kwargs["repository_id"])
    names = list(inspect.signature(fn).parameters)
    if names and names[0] == "repository_id" and args:
        return str(args[0])
    if isinstance(result, dict) and result.get("repository_id"):
        return str(result["repository_id"])
    return ""
