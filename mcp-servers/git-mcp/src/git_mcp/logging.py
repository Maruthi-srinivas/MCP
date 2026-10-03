"""One JSON log line per tool call. Arguments are not logged."""

import functools
import logging
import time
import uuid
from collections.abc import Callable

from investigator_shared.errors import ToolFailure, error_body

logger = logging.getLogger("git_mcp")


def _result_items(result: dict) -> int:
    if "error" in result:
        return 0
    for key in ("commits", "branches", "entries", "changed_paths"):
        if key in result:
            return len(result[key])
    return 1


def observed_tool(fn: Callable) -> Callable:
    """Log the call and turn ToolFailure into the public error object."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        request_id = "req_" + uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except ToolFailure as failure:
            _log(fn.__name__, request_id, started, "error", 0, failure.code)
            return error_body(failure, request_id)
        except Exception:
            _log(fn.__name__, request_id, started, "error", 0, "INTERNAL_ERROR")
            logger.exception("tool %s failed", fn.__name__)
            return error_body(ToolFailure("INTERNAL_ERROR", "Unexpected server error.", False), request_id)
        _log(fn.__name__, request_id, started, "success", _result_items(result), None)
        return result

    return wrapper


def _log(tool: str, request_id: str, started: float, status: str, result_items: int, error_code: str | None) -> None:
    payload = {
        "request_id": request_id,
        "mcp_server": "git-mcp",
        "tool": tool,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "status": status,
        "result_items": result_items,
    }
    if error_code:
        payload["error_code"] = error_code
    logger.info("%s", payload)
