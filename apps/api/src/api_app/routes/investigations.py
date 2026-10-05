"""Investigation sessions. The job loop runs the agent and stores the trace."""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api_app import db, jobs

router = APIRouter()


@router.post("/investigations")
async def start(body: dict, request: Request):
    caller = request.state.caller_id
    repository_id = str(body.get("repository_id") or "").strip()
    if not db.has_access(repository_id, caller):
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    row = db.get_repository_row(repository_id)
    if row is None:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown repository_id.", False)
    if row["status"] != "ready":
        return _error(409, "REPOSITORY_NOT_FOUND", "Repository is not ready.", False)
    question = str(body.get("question") or "").strip()
    prompt = str(body.get("prompt") or "").strip()
    if not question and not prompt:
        return _error(400, "INTERNAL_ERROR", "A question or prompt is required.", False)
    arguments = body.get("arguments") if isinstance(body.get("arguments"), dict) else {}
    session_id = str(uuid.uuid4())
    user_text = question or prompt
    db.insert_session(session_id, repository_id, caller, [{"role": "user", "text": user_text}])
    job_id = jobs.enqueue(
        "investigate",
        repository_id,
        {"session_id": session_id, "question": question, "prompt": prompt, "arguments": arguments},
        None,
        caller,
    )
    return JSONResponse({"session_id": session_id, "job_id": job_id}, status_code=202)


@router.post("/investigations/{session_id}/messages")
async def add_message(session_id: str, body: dict, request: Request):
    session = db.get_session(session_id)
    if session is None or session.get("caller_id") != request.state.caller_id:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown investigation.", False)
    question = str(body.get("question") or "").strip()
    prompt = str(body.get("prompt") or "").strip()
    if not question and not prompt:
        return _error(400, "INTERNAL_ERROR", "A question or prompt is required.", False)
    arguments = body.get("arguments") if isinstance(body.get("arguments"), dict) else {}
    messages = list(session["messages"] or [])
    messages.append({"role": "user", "text": question or prompt})
    db.save_messages(session_id, messages)
    job_id = jobs.enqueue(
        "investigate",
        session["repository_id"],
        {"session_id": session_id, "question": question, "prompt": prompt, "arguments": arguments},
        None,
        request.state.caller_id,
    )
    return JSONResponse({"session_id": session_id, "job_id": job_id}, status_code=202)


@router.get("/investigations/{session_id}")
async def get_investigation(session_id: str, request: Request):
    session = db.get_session(session_id)
    if session is None or session.get("caller_id") != request.state.caller_id:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown investigation.", False)
    job = db.latest_session_job(session_id)
    return {
        "session_id": session_id,
        "repository_id": session["repository_id"],
        "messages": list(session["messages"] or []),
        "job": None
        if job is None
        else {
            "id": str(job["id"]),
            "status": job["status"],
            "error_code": job["error_code"],
        },
    }


@router.get("/investigations/{session_id}/trace")
async def trace(session_id: str, request: Request):
    session = db.get_session(session_id)
    if session is None or session.get("caller_id") != request.state.caller_id:
        return _error(404, "REPOSITORY_NOT_FOUND", "Unknown investigation.", False)
    rows = []
    for item in db.list_tool_calls(session_id):
        arguments = item["arguments"] if isinstance(item["arguments"], dict) else {}
        rows.append(
            {
                "server": item["server"],
                "tool": item["tool"],
                "status": item["status"],
                "duration_ms": item["duration_ms"],
                "arguments": jobs.public_arguments(arguments),
                "argument_hash": item.get("argument_hash") or "",
            }
        )
    return {"session_id": session_id, "trace": rows}


def _error(status: int, code: str, message: str, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )
