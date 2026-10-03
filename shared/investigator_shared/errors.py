"""Errors both MCP servers return to clients."""

class ToolFailure(Exception):
    """A known tool failure with a stable code. Unexpected bugs are not this type."""

    def __init__(self, code: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def error_body(failure: ToolFailure, request_id: str) -> dict:
    """Shape required by the product error contract."""
    return {
        "error": {
            "code": failure.code,
            "message": failure.message,
            "retryable": failure.retryable,
            "request_id": request_id,
        }
    }
