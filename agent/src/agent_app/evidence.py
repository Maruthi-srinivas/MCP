"""Turn tool payloads into evidence. A missing file adds no row."""

def absorb(result: dict, tool: str, server: str, commit_sha: str) -> tuple[list[dict], str]:
    """Return high-confidence rows and the commit SHA if this result carried one."""
    if not isinstance(result, dict):
        return [], commit_sha
    if isinstance(result.get("resolved_commit"), str) and result["resolved_commit"]:
        commit_sha = result["resolved_commit"]
    if "error" in result:
        return [], commit_sha
    rows: list[dict] = []
    for match in result.get("matches") or []:
        _add(rows, tool, server, commit_sha, match.get("path"), match.get("line"), match.get("line"), "search hit")
    for definition in result.get("definitions") or []:
        _add(
            rows,
            tool,
            server,
            commit_sha,
            definition.get("path"),
            definition.get("start_line"),
            definition.get("end_line"),
            definition.get("name") or "definition",
        )
    if result.get("path") and "content" in result:
        _add(rows, tool, server, commit_sha, result.get("path"), result.get("start_line"), result.get("end_line"), "file read")
    for reference in result.get("references") or []:
        _add(rows, tool, server, commit_sha, reference.get("path"), reference.get("line"), reference.get("line"), "reference")
    for hint in result.get("hints") or []:
        _add(rows, tool, server, commit_sha, hint.get("file"), hint.get("line"), hint.get("line"), hint.get("library") or "database hint")
    return rows, commit_sha


def claims_from_model(claims: list[dict], known_files: set[str], tool: str, server: str, commit_sha: str) -> list[dict]:
    """Keep a model claim only when a tool already returned that file."""
    rows: list[dict] = []
    for claim in claims:
        path = claim.get("file") or ""
        if path not in known_files:
            continue
        rows.append(
            {
                "claim": claim.get("claim") or "",
                "file": path,
                "start_line": int(claim.get("start_line") or 1),
                "end_line": int(claim.get("end_line") or claim.get("start_line") or 1),
                "tool": tool,
                "mcp_server": server,
                "commit_sha": commit_sha,
                "confidence": "low",
            }
        )
    return rows


def known_files(evidence: list[dict]) -> set[str]:
    return {item["file"] for item in evidence if item.get("file")}


def _add(rows: list[dict], tool: str, server: str, commit_sha: str, path, start, end, claim: str) -> None:
    if not path or start is None:
        return
    end_line = end if end is not None else start
    rows.append(
        {
            "claim": f"{tool} returned {path}:{start}",
            "file": path,
            "start_line": int(start),
            "end_line": int(end_line),
            "tool": tool,
            "mcp_server": server,
            "commit_sha": commit_sha,
            "confidence": "high",
        }
    )
    del claim
