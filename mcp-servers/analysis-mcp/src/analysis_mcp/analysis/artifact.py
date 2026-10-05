"""Load or rebuild the sibling analysis file for one repository commit."""

import json
import time
from pathlib import Path

from investigator_shared.paths import repository_root
from investigator_shared.registry import get_repository, require_repository_id, workspace_root

from analysis_mcp.analysis import database, endpoints, entrypoints, external, graph, symbols
from analysis_mcp.analysis.embed import embed_texts, line_snippet
from analysis_mcp.analysis.vectors import store
from analysis_mcp.analysis.walk import parse_sources
from analysis_mcp.config import Settings, get_settings

ANALYZER_VERSION = "0.5.0"


def analysis_path(repository_id: str) -> Path:
    """JSON file beside the clone, not inside the git checkout."""
    require_repository_id(repository_id)
    return workspace_root() / f"{repository_id}.analysis.json"


def ensure_artifact(repository_id: str) -> dict:
    """Return the analysis for the stored commit, building it on first use."""
    record = get_repository(repository_id)
    commit_sha = record.get("resolved_commit") or ""
    path = analysis_path(repository_id)
    cached = _read_cached(path, commit_sha)
    if cached is not None:
        return cached
    root = repository_root(repository_id)
    built = build_artifact(root, commit_sha, get_settings(), time.monotonic())
    _attach_embeddings(root, built)
    store(repository_id, built.get("embeddings") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return built


def build_artifact(root: Path, commit_sha: str, settings: Settings, started: float) -> dict:
    """Parse the checkout and return a stable document. Caps set truncated and stop that list."""
    parsed, extra, warnings, truncated = parse_sources(root, settings, started)
    functions: list[dict] = []
    classes: list[dict] = []
    imports: list[dict] = []
    endpoint_rows: list[dict] = []
    hints: list[dict] = []
    services: list[dict] = []
    entrypoint_rows: list[dict] = []
    calls: list[dict] = []
    for path, tree in parsed:
        file_functions, file_classes, file_imports = symbols.collect(tree, path)
        functions.extend(file_functions)
        classes.extend(file_classes)
        imports.extend(file_imports)
        endpoint_rows.extend(endpoints.collect(tree, path))
        hints.extend(database.collect(tree, path))
        services.extend(external.collect(tree, path))
        entrypoint_rows.extend(entrypoints.collect(tree, path))
        calls.extend(graph.collect_calls(tree, path))
    functions.extend(extra["functions"])
    classes.extend(extra["classes"])
    imports.extend(extra["imports"])
    endpoint_rows.extend(extra["endpoints"])
    calls.extend(extra["calls"])

    capped = False
    functions, cut = _sort_cap(functions, lambda item: (item["path"], item["line"], item["name"], item["kind"]), settings.max_functions)
    capped = capped or cut
    classes, cut = _sort_cap(classes, lambda item: (item["path"], item["line"], item["name"]), settings.max_classes)
    capped = capped or cut
    imports, cut = _sort_cap(imports, lambda item: (item["path"], item["line"], item["module"], tuple(item["names"])), settings.max_functions)
    capped = capped or cut
    endpoint_rows, cut = _sort_cap(endpoint_rows, lambda item: (item["file"], item["line"], item["framework"], item["method"], item["path"]), settings.max_endpoints)
    capped = capped or cut
    hints, cut = _sort_cap(hints, lambda item: (item["file"], item["line"], item["library"], item["kind"]), settings.max_hints)
    capped = capped or cut
    services, cut = _sort_cap(services, lambda item: (item["file"], item["line"], item["library"], item.get("url", "")), settings.max_hints)
    capped = capped or cut
    truncated = truncated or capped
    entrypoint_rows = sorted(entrypoint_rows, key=lambda item: (item["path"], item["line"], item["reason"], item["name"]))
    if capped:
        warnings.append({"path": ".", "message": "A collection reached its cap. Later items were omitted."})

    files = {path for path, _tree in parsed}
    files.update(item["path"] for item in functions + classes + imports)
    nodes, edges, edges_cut = graph.build(functions, imports, calls, files, settings.max_edges)
    truncated = truncated or edges_cut
    if edges_cut:
        warnings.append({"path": ".", "message": "Graph edge cap reached. Later edges were omitted."})
    warnings.sort(key=lambda item: (item["path"], item["message"]))

    return {
        "analyzer_version": ANALYZER_VERSION,
        "commit_sha": commit_sha,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "endpoints": endpoint_rows,
        "database_hints": hints,
        "external_services": services,
        "entrypoints": entrypoint_rows,
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
        "truncated": truncated,
    }


def summary(repository_id: str, artifact: dict) -> dict:
    """Counts and warnings. The lists stay on the other tools."""
    return {
        "repository_id": repository_id,
        "commit_sha": artifact["commit_sha"],
        "analyzer_version": artifact["analyzer_version"],
        "counts": {
            "functions": len(artifact["functions"]),
            "classes": len(artifact["classes"]),
            "imports": len(artifact["imports"]),
            "endpoints": len(artifact["endpoints"]),
            "database_hints": len(artifact["database_hints"]),
            "external_services": len(artifact["external_services"]),
            "entrypoints": len(artifact["entrypoints"]),
            "edges": len(artifact["edges"]),
            "warnings": len(artifact["warnings"]),
        },
        "warnings": artifact["warnings"],
        "truncated": artifact["truncated"],
    }


def page_items(items: list[dict], page: int, page_size: int) -> tuple[list[dict], bool]:
    start = (page - 1) * page_size
    window = items[start : start + page_size + 1]
    return window[:page_size], len(window) > page_size


def _attach_embeddings(root: Path, artifact: dict) -> None:
    """One vector per function and class. The architecture resource leaves this list out."""
    rows: list[dict] = []
    seen: set[tuple] = set()
    for item in artifact["functions"] + artifact["classes"]:
        kind = item.get("kind") or "class"
        key = (item["path"], item["name"], item["line"], kind)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": item["name"],
                "kind": kind,
                "path": item["path"],
                "start_line": item["line"],
                "snippet": line_snippet(root, item["path"], item["line"]),
            }
        )
    if not rows:
        artifact["embeddings"] = []
        return
    vectors = embed_texts([f"{row['name']} {row['snippet']}" for row in rows])
    for row, vector in zip(rows, vectors):
        row["vector"] = vector
    artifact["embeddings"] = rows


def _sort_cap(items: list[dict], key, limit: int) -> tuple[list[dict], bool]:
    ordered = sorted(items, key=key)
    if len(ordered) <= limit:
        return ordered, False
    return ordered[:limit], True


def _read_cached(path: Path, commit_sha: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("commit_sha") != commit_sha or data.get("analyzer_version") != ANALYZER_VERSION:
        return None
    return data

