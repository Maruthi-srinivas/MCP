"""Live check used by `docker compose --profile smoke run --rm smoke`."""

import os
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("SMOKE_BASE_URL"),
    reason="Set SMOKE_BASE_URL to call the running repository-mcp service.",
)


def test_live_health():
    _check(os.environ["SMOKE_BASE_URL"])
    git_url = os.environ.get("GIT_SMOKE_BASE_URL", "").strip()
    if git_url:
        _check(git_url)
    analysis_url = os.environ.get("ANALYSIS_SMOKE_BASE_URL", "").strip()
    if analysis_url:
        _check(analysis_url)
    agent_url = os.environ.get("AGENT_SMOKE_BASE_URL", "").strip()
    if agent_url:
        _check(agent_url)


def _check(base_url: str) -> None:
    url = base_url.rstrip("/") + "/health"
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read()
    assert response.status == 200
    assert b'"status": "ok"' in body or b'"status":"ok"' in body
