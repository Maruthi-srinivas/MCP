"""Import and analysis routes."""

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
import psycopg

from api_app import db, jobs, quotas
from api_app.config import get_settings
from api_app.ids import repository_identity
from api_app.mcp_client import call_tool
from api_app.paths import unsafe_path
from api_app.rate_limit import allow

router = APIRouter()


@router.post("/repositories")
async def import_repository(
    body: dict,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    caller = request.state.caller_id
    url = str(body.get("url") or "").strip()
    if not url:
        return _error(400, "INVALID_REPOSITORY_URL", "A repository url is required.", False)
    ref = str(body.get("ref")).strip() if body.get("ref") else None
    key = idempotency_key.strip() if idempotency_key else None
    if key:
        existing = db.find_job_by_key(caller, key)
        if existing:
            return JSONResponse(
                {"repository_id": existing["repository_id"], "job_id": str(existing["id"])},
                status_code=200,
            )
    if not allow("import", get_settings().imports_per_minute):
        return _error(429, "RATE_LIMITED", "Import rate limit reached.", True)
    if not quotas.acquire_import(caller):
        return _error(429, "QUOTA_EXCEEDED", "Too many imports are running.", True)
    repository_id, _canonical, owner, name = repository_identity(url, ref)
    db.ensure_repository_stub(repository_id, url, owner, name, ref)
    db.grant_access(repository_id, caller)
    try:
        job_id = jobs.enqueue(
            "import",
            repository_id,
            {"url": url, "ref": ref},
            key,
            caller,
        )
    except psycopg.errors.UniqueViolation:
        quotas.release_import(caller)
        existing = db.find_job_by_key(caller, key or "")
        if existing:
            return JSONResponse(
                {"repository_id": existing["repository_id"], "job_id": str(existing["id"])},
                status_code=200,
            )
        raise
    except Exception:
        quotas.release_import(caller)
        raise
    return JSONResponse({"repository_id": repository_id, "job_id": job_id}, status_code=202)


@router.get("/repositories")
async def list_repositories(request: Request):
    rows = []
    for row in db.list_repositories(request.state.caller_id):
        rows.append(
            {
                "repository_id": row["repository_id"],
                "url": row["url"],
                "owner": row["owner"],
                "name": row["name"],
                "ref": row["ref"],
                "resolved_commit": row["resolved_commit"],
                "status": row["status"],
            }
        )
    return {"repositories": rows}


@router.get("/repositories/{repository_id}")
async def get_repository(repository_id: str, request: Request):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return {
        "repository_id": row["repository_id"],
        "url": row["url"],
        "owner": row["owner"],
        "name": row["name"],
        "ref": row["ref"],
        "resolved_commit": row["resolved_commit"],
        "status": row["status"],
    }


@router.get("/repositories/{repository_id}/status")
async def repository_status(repository_id: str, request: Request):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    job = db.latest_job(repository_id)
    row = db.get_repository_row(repository_id)
    if job is None and row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    payload = (job or {}).get("payload") or {}
    return {
        "repository_id": repository_id,
        "status": row["status"] if row else (job or {}).get("status"),
        "job": None
        if job is None
        else {
            "id": str(job["id"]),
            "kind": job["kind"],
            "status": job["status"],
            "error_code": job["error_code"],
            "cache_hit": bool(payload.get("cache_hit")),
        },
    }


@router.post("/repositories/{repository_id}/analyze")
async def analyze(repository_id: str, request: Request):
    caller = request.state.caller_id
    if not db.has_access(repository_id, caller):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    if db.count_analysis_jobs(repository_id) >= get_settings().max_analysis_jobs:
        return _error(429, "QUOTA_EXCEEDED", "This repository has too many analysis jobs.", False)
    if not allow("analyze", get_settings().analyses_per_minute):
        return _error(429, "RATE_LIMITED", "Analysis rate limit reached.", True)
    job_id = jobs.enqueue("analyze", repository_id, {}, None, caller)
    return JSONResponse({"repository_id": repository_id, "job_id": job_id}, status_code=202)


@router.get("/repositories/{repository_id}/architecture")
async def architecture(repository_id: str, request: Request):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    stored = db.latest_architecture(repository_id)
    if stored is None:
        return {"repository_id": repository_id, "status": "not_ready"}
    return {
        "repository_id": repository_id,
        "status": "ready",
        "commit_sha": stored["commit_sha"],
        "analyzer_version": stored["analyzer_version"],
        "architecture": stored["body"],
    }


@router.get("/repositories/{repository_id}/overview")
async def overview(repository_id: str, request: Request):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    stored = db.latest_architecture(repository_id)
    body = (stored or {}).get("body") or {}
    if isinstance(body, str):
        body = {}
    frameworks = []
    for item in body.get("entrypoints") or []:
        name = item.get("name") or ""
        if name and name not in frameworks:
            frameworks.append(name)
    services = []
    for item in body.get("external_services") or []:
        name = item.get("library") or ""
        if name and name not in services:
            services.append(name)
    return {
        "repository_id": row["repository_id"],
        "url": row["url"],
        "owner": row["owner"],
        "name": row["name"],
        "ref": row["ref"],
        "resolved_commit": row["resolved_commit"],
        "status": row["status"],
        "languages": db.list_languages(repository_id),
        "dependencies": [
            {"name": item["name"], "version": item["version"], "source": item["source"]}
            for item in db.list_dependencies(repository_id)
        ],
        "frameworks": frameworks,
        "services": services,
        "analysis_status": "ready" if stored else "not_ready",
        "analyzer_version": (stored or {}).get("analyzer_version") or "",
        "analysis_commit": (stored or {}).get("commit_sha") or "",
    }


@router.get("/repositories/{repository_id}/jobs")
async def repository_jobs(repository_id: str, request: Request):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    return {
        "repository_id": repository_id,
        "jobs": [
            {
                "id": str(item["id"]),
                "kind": item["kind"],
                "status": item["status"],
                "error_code": item["error_code"],
            }
            for item in db.list_jobs(repository_id)
        ],
    }


@router.get("/repositories/{repository_id}/file")
async def repository_file(
    repository_id: str,
    request: Request,
    path: str = Query(default=""),
    start_line: int = Query(default=1),
):
    if not db.has_access(repository_id, request.state.caller_id):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    if unsafe_path(path):
        return _error(400, "INVALID_PATH", "Path escapes the repository.", False)
    read = await call_tool(
        "read_file",
        {"repository_id": repository_id, "path": path.strip(), "start_line": start_line},
    )
    if read.get("error"):
        error = read["error"]
        code = error.get("code") or "INTERNAL_ERROR"
        status = 404 if code in {"REPOSITORY_NOT_FOUND", "FILE_NOT_FOUND"} else 400
        return _error(status, code, error.get("message") or "The file could not be read.", bool(error.get("retryable")))
    return {
        "repository_id": repository_id,
        "path": read.get("path") or path,
        "start_line": read.get("start_line"),
        "end_line": read.get("end_line"),
        "content": read.get("content") or "",
        "truncated": bool(read.get("truncated")),
        "total_lines": read.get("total_lines"),
    }


def _error(status: int, code: str, message: str, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )
