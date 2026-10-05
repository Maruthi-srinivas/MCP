"""One key=value log line per tool call. Arguments are not logged."""

import functools
import logging
import time
import uuid
from collections.abc import Callable

from investigator_shared.errors import ToolFailure, error_body
from investigator_shared.secrets import log_event

from git_mcp.metrics import record

logger = logging.getLogger("git_mcp")


def observed_tool(fn: Callable) -> Callable:
    """Log the call and turn ToolFailure into the public error object."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        request_id = "req_" + uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except ToolFailure as failure:
            _log(fn.__name__, request_id, started, "error", failure.code, args, kwargs, None)
            return error_body(failure, request_id)
        except Exception:
            _log(fn.__name__, request_id, started, "error", "INTERNAL_ERROR", args, kwargs, None)
            logger.exception("tool %s failed", fn.__name__)
            return error_body(ToolFailure("INTERNAL_ERROR", "Unexpected server error.", False), request_id)
        _log(fn.__name__, request_id, started, "success", None, args, kwargs, result)
        return result

    return wrapper


def _log(tool, request_id, started, status, error_code, args, kwargs, result) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    record(tool, duration_ms, status)
    log_event(
        "tool_call",
        duration_ms=duration_ms,
        status=status,
        request_id=request_id,
        repository_id=_repository_id(args, kwargs),
        tool=tool,
        error_code=error_code,
    )


def _repository_id(args: tuple, kwargs: dict) -> str:
    if kwargs.get("repository_id"):
        return str(kwargs["repository_id"])
    if args:
        return str(args[0])
    return ""
