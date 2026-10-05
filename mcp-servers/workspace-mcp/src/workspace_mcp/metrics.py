"""In-memory counters and histograms for this process. A restart clears them."""

import threading

_lock = threading.Lock()
_counters: dict[str, int] = {}
_histograms: dict[str, dict] = {}


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + amount


def record(name: str, duration_ms: int, status: str) -> None:
    """Count the call and add its duration to the histogram."""
    increment(f"{name}_calls")
    if status not in {"ok", "success", "succeeded"}:
        increment(f"{name}_errors")
    with _lock:
        hist = _histograms.setdefault(
            name,
            {"count": 0, "sum_ms": 0, "max_ms": 0, "buckets": {"lt_100ms": 0, "lt_1s": 0, "rest": 0}},
        )
        hist["count"] += 1
        hist["sum_ms"] += int(duration_ms)
        hist["max_ms"] = max(hist["max_ms"], int(duration_ms))
        if duration_ms < 100:
            hist["buckets"]["lt_100ms"] += 1
        elif duration_ms < 1000:
            hist["buckets"]["lt_1s"] += 1
        else:
            hist["buckets"]["rest"] += 1


def snapshot() -> dict:
    with _lock:
        histograms = {
            name: {**body, "buckets": dict(body["buckets"])}
            for name, body in _histograms.items()
        }
    return {"service": "workspace-mcp", "counters": dict(_counters), "histograms": histograms}
