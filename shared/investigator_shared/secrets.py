"""Remove obvious secrets from text that a resource returns."""

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
