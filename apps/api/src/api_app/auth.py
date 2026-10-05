"""Map the two local tokens to caller ids. The token is never stored."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api_app.config import get_settings

router = APIRouter()
OPEN_PATHS = {"/health", "/ready"}


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
        if scope.get("method") == "OPTIONS" or scope.get("path") in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers") or []}
        caller = caller_id(headers.get("authorization"))
        if caller is None:
            await unauthorized()(scope, receive, send)
            return
        scope.setdefault("state", {})["caller_id"] = caller
        await self.app(scope, receive, send)


@router.get("/me")
async def me(request: Request):
    """The caller id for the token in memory. The token itself is not returned."""
    return {"caller_id": request.state.caller_id}
