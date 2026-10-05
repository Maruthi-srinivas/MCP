"""Remove obvious secrets from text that a resource or a log line returns."""

import logging
import re

_ASSIGNMENT = re.compile(
    r"^(\s*)([A-Za-z_][A-Za-z0-9_]*(?:_KEY|_TOKEN|_SECRET))\s*=\s*.+$",
    re.MULTILINE,
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


def redact(text: str) -> str:
    """Replace secret assignments and private-key blocks. The name of the setting stays."""
    without_keys = _PRIVATE_KEY.sub("[redacted private key]", text)

    def _hide(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)} = [redacted]"

    return _ASSIGNMENT.sub(_hide, without_keys)


class RedactingFilter(logging.Filter):
    """Run log messages through the same redaction as file text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def install_redacting_logs() -> None:
    logging.getLogger().addFilter(RedactingFilter())


_LOG_FIELDS = ("request_id", "session_id", "repository_id", "tool", "error_code")


def log_event(event: str, *, duration_ms: int = 0, status: str = "ok", **fields: object) -> None:
    """One key=value line. Tokens and raw tool arguments are not fields."""
    parts = [f"event={event}", f"duration_ms={int(duration_ms)}", f"status={status}"]
    for key in _LOG_FIELDS:
        value = fields.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    logging.getLogger("investigator").info(redact(" ".join(parts)))
