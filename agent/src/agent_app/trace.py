"""In-memory trace for this process. Full storage is a later version."""

import hashlib
import json

_STEPS: list[dict] = []


def remember(steps: list[dict], limit: int) -> None:
    """Keep the newest steps only. Arguments stored here are already summaries."""
    _STEPS.extend(steps)
    overflow = len(_STEPS) - limit
    if overflow > 0:
        del _STEPS[:overflow]


def recent() -> list[dict]:
    return list(_STEPS)


def argument_hash(arguments: dict) -> str:
    """sha256 of the raw arguments. The hex digest is safe to store and return."""
    raw = json.dumps(arguments, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def argument_summary(arguments: dict) -> dict:
    """Keep identifiers. Drop file bodies, patches, and secrets."""
    summary: dict = {}
    if arguments.get("repository_id"):
        summary["repository_id"] = arguments["repository_id"]
    if arguments.get("path"):
        summary["path"] = arguments["path"]
    if arguments.get("name"):
        summary["name"] = arguments["name"]
    elif arguments.get("symbol"):
        summary["name"] = arguments["symbol"]
    if arguments.get("ref"):
        summary["ref"] = arguments["ref"]
    return summary
