"""Reject a request body larger than the configured byte cap."""

from fastapi.responses import JSONResponse

from api_app.config import get_settings


class BodyLimit:
    """Check Content-Length before the route reads the body."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().max_body_bytes
        for key, value in scope.get("headers") or []:
            if key.lower() == b"content-length" and int(value) > limit:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "QUOTA_EXCEEDED",
                            "message": "The request body is too large.",
                            "retryable": False,
                        }
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
