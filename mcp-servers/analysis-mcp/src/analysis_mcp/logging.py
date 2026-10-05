"""One key=value log line per tool call. Arguments are not logged."""

import functools
import logging
import time
import uuid
from collections.abc import Callable

from investigator_shared.errors import ToolFailure, error_body
from investigator_shared.secrets import log_event

from analysis_mcp.metrics import record

logger = logging.getLogger("analysis_mcp")


def observed_tool(fn: Callable) -> Callable:
    """Log the call and turn ToolFailure into the public error object."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        request_id = "req_" + uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except ToolFailure as failure:
            _log(fn.__name__, request_id, started, "error", failure.code, args, kwargs)
            return error_body(failure, request_id)
        except Exception:
            _log(fn.__name__, request_id, started, "error", "INTERNAL_ERROR", args, kwargs)
            logger.exception("tool %s failed", fn.__name__)
            return error_body(ToolFailure("INTERNAL_ERROR", "Unexpected server error.", False), request_id)
        _log(fn.__name__, request_id, started, "success", None, args, kwargs)
        return result

    return wrapper


def _log(tool, request_id, started, status, error_code, args, kwargs) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    record(tool, duration_ms, status)
    if tool == "analyze_code":
        record("analysis", duration_ms, status)
    repository_id = ""
    if kwargs.get("repository_id"):
        repository_id = str(kwargs["repository_id"])
    elif args:
        repository_id = str(args[0])
    log_event(
        "tool_call",
        duration_ms=duration_ms,
        status=status,
        request_id=request_id,
        repository_id=repository_id,
        tool=tool,
        error_code=error_code,
    )
