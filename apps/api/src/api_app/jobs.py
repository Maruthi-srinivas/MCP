"""Background loop. Clone and analysis run here, then the rows are stored."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

import httpx

from investigator_shared.secrets import log_event

from api_app import cache, db, quotas
from api_app.metrics import increment, record
from api_app.cleanup import expire_workspaces
from api_app.config import get_settings
from api_app.files import list_files
from api_app.mcp_client import call_tool, read_json

log = logging.getLogger("api")
_cleanup_tick = 0


async def run_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        _maybe_enqueue_cleanup()
        job = db.claim_job()
        if job is None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except TimeoutError:
                continue
            return
        try:
            await _run(job)
        except Exception:
            log.exception("job failed id=%s", job["id"])
            db.finish_job(str(job["id"]), "failed", "INTERNAL_ERROR")


def enqueue(
    kind: str,
    repository_id: str | None,
    payload: dict,
    idempotency_key: str | None,
    caller_id: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    db.insert_job(
        {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "repository_id": repository_id,
            "idempotency_key": idempotency_key,
            "payload": payload,
            "caller_id": caller_id,
        }
    )
    return job_id


async def _run(job: dict) -> None:
    kind = job["kind"]
    if kind == "import":
        await _import(job)
        return
    if kind == "analyze":
        await _analyze(job)
        return
    if kind == "investigate":
        await _investigate(job)
        return
    if kind == "cleanup":
        expire_workspaces()
        db.finish_job(str(job["id"]), "succeeded", None)
        return
    db.finish_job(str(job["id"]), "failed", "INTERNAL_ERROR")


async def _import(job: dict) -> None:
    payload = _payload(job)
    try:
        await _clone(job, payload)
    finally:
        if job.get("caller_id"):
            quotas.release_import(job["caller_id"])


async def _clone(job: dict, payload: dict) -> None:
    started = time.perf_counter()
    status = "failed"
    repository_id = ""
    try:
        await _clone_body(job, payload)
        status = "succeeded"
        repository_id = str(job.get("repository_id") or "")
    except _Stopped:
        repository_id = str(job.get("repository_id") or "")
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        record("import", duration_ms, status)
        log_event("import", duration_ms=duration_ms, status=status, repository_id=repository_id)


async def _clone_body(job: dict, payload: dict) -> None:
    arguments = {"repository_url": payload["url"]}
    if payload.get("ref"):
        arguments["ref"] = payload["ref"]
    cloned = await call_tool("clone_repository", arguments)
    if cloned.get("error"):
        db.finish_job(str(job["id"]), "failed", cloned["error"].get("code") or "CLONE_FAILED")
        raise _Stopped()
    repository_id = cloned["repository_id"]
    db.remember_idempotency(repository_id, job.get("idempotency_key"))
    root = Path(cloned["workspace_path"])
    db.replace_files(repository_id, list_files(root, get_settings().max_file_rows))
    structure = await read_json(f"repo://{repository_id}/structure")
    dependencies = await read_json(f"repo://{repository_id}/dependencies")
    if structure.get("error") or dependencies.get("error"):
        code = (structure.get("error") or dependencies.get("error") or {}).get("code") or "INTERNAL_ERROR"
        db.finish_job(str(job["id"]), "failed", code)
        raise _Stopped()
    db.replace_symbols(repository_id, structure.get("symbols") or [])
    db.replace_dependencies(
        repository_id,
        [
            {
                "name": item["name"],
                "version": item.get("version") or "",
                "source": item.get("source_file") or "",
            }
            for item in dependencies.get("dependencies") or []
        ],
    )
    job["repository_id"] = repository_id
    db.finish_job(str(job["id"]), "succeeded", None, {**payload, "repository_id": repository_id})


async def _analyze(job: dict) -> None:
    started = time.perf_counter()
    status = await _analyze_body(job)
    if status == "queued":
        return
    duration_ms = int((time.perf_counter() - started) * 1000)
    record("analysis", duration_ms, status)
    log_event(
        "analysis",
        duration_ms=duration_ms,
        status=status,
        repository_id=str(job.get("repository_id") or ""),
    )


async def _analyze_body(job: dict) -> str:
    repository_id = job["repository_id"]
    lock = cache.lock_key(repository_id)
    if not cache.acquire(lock):
        await asyncio.sleep(0.5)
        db.finish_job(str(job["id"]), "queued", None)
        return "queued"
    try:
        row = db.get_repository_row(repository_id)
        if row is None:
            db.finish_job(str(job["id"]), "failed", "REPOSITORY_NOT_FOUND")
            return "failed"
        commit = row["resolved_commit"]
        version = get_settings().analyzer_version
        cached = cache.get_json(cache.analysis_key(repository_id, commit, version))
        search_arguments = {"repository_id": repository_id, "query": "def"}
        search_cache_key = cache.tool_key(repository_id, commit, "search_code", search_arguments)
        if cache.get_json(search_cache_key) is not None:
            increment("cache_hits")
            cache.note_hit("search_code", search_cache_key)
        else:
            found = await call_tool("search_code", search_arguments)
            if not found.get("error"):
                cache.set_json(search_cache_key, {"ok": True})
        if cached is not None:
            increment("cache_hits")
            cache.note_hit("analyze_code", cache.analysis_key(repository_id, commit, version))
            payload = _payload(job)
            payload["cache_hit"] = True
            db.finish_job(str(job["id"]), "succeeded", None, payload)
            return "succeeded"
        analyzed = await call_tool("analyze_code", {"repository_id": repository_id})
        if analyzed.get("error"):
            db.finish_job(str(job["id"]), "failed", analyzed["error"].get("code") or "INTERNAL_ERROR")
            return "failed"
        architecture = await read_json(f"repo://{repository_id}/architecture")
        if architecture.get("error"):
            db.finish_job(str(job["id"]), "failed", architecture["error"].get("code") or "INTERNAL_ERROR")
            return "failed"
        version = architecture.get("analyzer_version") or analyzed.get("analyzer_version") or ""
        db.insert_analysis(repository_id, commit, version, architecture)
        cache.set_json(
            cache.analysis_key(repository_id, commit, version),
            {"analyzer_version": version, "body": architecture},
        )
        payload = _payload(job)
        payload["cache_hit"] = False
        db.finish_job(str(job["id"]), "succeeded", None, payload)
        return "succeeded"
    finally:
        cache.release(lock)


class _Stopped(Exception):
    """The job already stored its failure. The timer still records it."""


async def _investigate(job: dict) -> None:
    started = time.perf_counter()
    payload = _payload(job)
    session_id = payload.get("session_id") or ""
    session = db.get_session(session_id)
    if session is None:
        db.finish_job(str(job["id"]), "failed", "REPOSITORY_NOT_FOUND")
        record("investigation", int((time.perf_counter() - started) * 1000), "failed")
        log_event("investigation", duration_ms=int((time.perf_counter() - started) * 1000), status="failed", session_id=session_id)
        return
    body = {"repository_id": session["repository_id"], "session_id": session_id}
    if payload.get("question"):
        body["question"] = payload["question"]
    if payload.get("prompt"):
        body["prompt"] = payload["prompt"]
    if payload.get("arguments"):
        body["arguments"] = payload["arguments"]
    result = await _ask_agent(body)
    messages = list(session["messages"] or [])
    messages.append(
        {
            "role": "assistant",
            "text": result.get("answer") or "",
            "evidence": public_evidence(result.get("evidence") or []),
        }
    )
    db.save_messages(session_id, messages)
    start = db.next_position(session_id)
    rows = []
    for offset, step in enumerate(result.get("trace") or []):
        rows.append(
            {
                "position": start + offset,
                "server": step.get("server") or "",
                "tool": step.get("tool") or "",
                "status": step.get("status") or "",
                "duration_ms": step.get("duration_ms") or 0,
                "arguments": public_arguments(step.get("arguments") or {}),
                "argument_hash": step.get("argument_hash") or "",
            }
        )
    db.insert_tool_calls(session_id, rows)
    db.claim_proposals(session_id, session.get("caller_id") or "")
    steps = len(result.get("trace") or [])
    increment("investigation_steps", steps)
    duration_ms = int((time.perf_counter() - started) * 1000)
    if result.get("stopped_reason") == "max_tool_calls":
        db.finish_job(str(job["id"]), "failed", "QUOTA_EXCEEDED", payload)
        record("investigation", duration_ms, "failed")
        log_event(
            "investigation",
            duration_ms=duration_ms,
            status="failed",
            session_id=session_id,
            repository_id=session["repository_id"],
        )
        return
    db.finish_job(str(job["id"]), "succeeded", None, payload)
    record("investigation", duration_ms, "succeeded")
    log_event(
        "investigation",
        duration_ms=duration_ms,
        status="succeeded",
        session_id=session_id,
        repository_id=session["repository_id"],
    )


async def _ask_agent(body: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{get_settings().agent_url}/investigate", json=body)
    response.raise_for_status()
    return response.json()


def public_arguments(arguments: dict) -> dict:
    kept = {}
    for key in ("repository_id", "path", "name", "ref", "proposal_id"):
        if arguments.get(key):
            kept[key] = arguments[key]
    return kept


def public_evidence(rows: list) -> list[dict]:
    kept = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("file"):
            continue
        start = int(item.get("start_line") or 1)
        kept.append(
            {
                "file": item["file"],
                "start_line": start,
                "end_line": int(item.get("end_line") or start),
                "tool": item.get("tool") or "",
                "mcp_server": item.get("mcp_server") or "",
            }
        )
    return kept


def _payload(job: dict) -> dict:
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)


def _maybe_enqueue_cleanup() -> None:
    global _cleanup_tick
    _cleanup_tick += 1
    if _cleanup_tick < 60:
        return
    _cleanup_tick = 0
    if db.cleanup_job_pending():
        return
    enqueue("cleanup", None, {}, None)
