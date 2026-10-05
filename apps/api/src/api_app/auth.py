"""Map the two local tokens to caller ids. The token is never stored."""

import re
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from investigator_shared.secrets import log_event

from api_app.config import get_settings

router = APIRouter()
OPEN_PATHS = {"/health", "/ready", "/metrics"}
_REPOSITORY = re.compile(r"/repositories/(repo_[0-9a-f]+)")


def caller_id(authorization: str | None) -> str | None:
    """Return alice or bob, or None when the bearer token is missing or unknown."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    settings = get_settings()
    secret = token.strip()
    if secret and secret == settings.alice_token:
        return "alice"
    if secret and secret == settings.bob_token:
        return "bob"
    return None


def unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "UNAUTHORIZED", "message": "A bearer token is required.", "retryable": False}},
        status_code=401,
    )


class AuthGate:
    """Reject requests that do not map to alice or bob. Health stays open."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if scope.get("method") == "OPTIONS" or path in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers") or []}
        caller = caller_id(headers.get("authorization"))
        if caller is None:
            await unauthorized()(scope, receive, send)
            return
        scope.setdefault("state", {})["caller_id"] = caller
        await _call_and_log(self.app, scope, receive, send, path)


async def _call_and_log(app, scope, receive, send, path: str) -> None:
    """Time the request and log it. The request id is not stored."""
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    status = {"code": 500}

    async def send_with_status(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        await send(message)

    await app(scope, receive, send_with_status)
    found = _REPOSITORY.search(path)
    log_event(
        "http_request",
        duration_ms=int((time.perf_counter() - started) * 1000),
        status=str(status["code"]),
        request_id=request_id,
        repository_id=found.group(1) if found else "",
    )


@router.get("/me")
async def me(request: Request):
    """The caller id for the token in memory. The token itself is not returned."""
    return {"caller_id": request.state.caller_id}
