"""Bounded ripgrep search. The process is stopped once the hit limit is reached."""

import json
import subprocess
from pathlib import Path

from repository_mcp.config import Settings
from repository_mcp.errors import ToolFailure


def search_workspace(
    root: Path,
    query: str,
    file_pattern: str | None,
    settings: Settings,
) -> tuple[list[dict], bool]:
    """Return up to max_search_hits matches and whether more existed."""
    command = [
        "rg",
        "--json",
        "--max-columns",
        "200",
        "--max-filesize",
        str(settings.max_file_bytes),
        "--glob",
        "!.git/**",
        "--glob",
        "!.git",
    ]
    if file_pattern:
        command.extend(["--glob", file_pattern])
    command.extend(["--", query, str(root)])

    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ToolFailure("INTERNAL_ERROR", "ripgrep is not available in this image.", False) from exc

    matches: list[dict] = []
    truncated = False
    try:
        assert process.stdout is not None
        for line in process.stdout:
            event = _parse_event(line)
            if event is None:
                continue
            if len(matches) >= settings.max_search_hits:
                truncated = True
                process.kill()
                break
            event["path"] = _relative_to_root(root, event["path"])
            matches.append(event)
        stderr = ""
        if process.stderr is not None:
            try:
                stderr = process.stderr.read()
            except Exception:
                stderr = ""
        return_code = process.wait(timeout=settings.tool_timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise ToolFailure("TOOL_TIMEOUT", "Search exceeded the configured deadline.", True) from exc

    if return_code not in (0, 1) and not truncated:
        detail = (stderr or "Search failed.").strip().splitlines()
        summary = detail[-1] if detail else "Search failed."
        raise ToolFailure("INTERNAL_ERROR", summary[:300], False)
    return matches, truncated


def _relative_to_root(root: Path, raw: str) -> str:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(raw).name


def _parse_event(line: str) -> dict | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if event.get("type") != "match":
        return None
    data = event.get("data", {})
    path_data = data.get("path", {})
    path_text = path_data.get("text")
    if not path_text:
        return None
    lines = data.get("lines", {}).get("text", "")
    snippet = lines.replace("\n", " ").strip()
    if len(snippet) > 200:
        snippet = snippet[:200]
    return {
        "path": path_text,
        "line": data.get("line_number"),
        "snippet": snippet,
    }
