"""Contract tests against the Compose API, Postgres, and Redis."""

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import psycopg
import pytest
import redis

from api_app.cleanup import expire_workspaces

API = os.environ["API_BASE_URL"].rstrip("/")
FIXTURE_URL = "file:///fixtures/service_app"
ALICE = os.environ.get("ALICE_TOKEN", "alice-local-token")
BOB = os.environ.get("BOB_TOKEN", "bob-local-token")


def post(url: str, token: str = ALICE, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(kwargs.pop("headers", {}) or {})
    return httpx.post(url, headers=headers, **kwargs)


def get(url: str, token: str = ALICE, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(kwargs.pop("headers", {}) or {})
    return httpx.get(url, headers=headers, **kwargs)


@pytest.fixture(scope="session")
def fixture_repo():
    source = Path(os.environ["FIXTURE_SOURCE"])
    destination = Path(os.environ["FIXTURE_DEST"])
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    _git(destination, "init")
    _git(destination, "add", ".")
    _git(destination, "commit", "-m", "init")
    return destination


@pytest.fixture(scope="session")
def imported(fixture_repo):
    del fixture_repo
    headers = {"Idempotency-Key": f"import-{uuid.uuid4()}"}
    first = post(f"{API}/repositories", json={"url": FIXTURE_URL}, headers=headers, timeout=30)
    second = post(f"{API}/repositories", json={"url": FIXTURE_URL}, headers=headers, timeout=30)
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["repository_id"] == second.json()["repository_id"]
    assert first.json()["job_id"] == second.json()["job_id"]
    record = _wait_ready(first.json()["repository_id"], first.json()["job_id"])
    _clear_analysis_jobs(record["repository_id"])
    return record


def test_idempotent_import_returns_one_repository(imported):
    assert imported["status"] == "ready"
    assert imported["resolved_commit"]


def test_second_analyze_is_a_cache_hit(imported):
    repository_id = imported["repository_id"]
    first = _analyze(repository_id)
    assert first["cache_hit"] is False
    before = get(f"{API}/repositories/{repository_id}/architecture", timeout=30).json()
    second = _analyze(repository_id)
    assert second["cache_hit"] is True
    after = get(f"{API}/repositories/{repository_id}/architecture", timeout=30).json()
    assert before["status"] == "ready"
    assert after["architecture"] == before["architecture"]
    assert after["commit_sha"] == before["commit_sha"]


def test_investigation_trace_appends_messages(imported):
    repository_id = imported["repository_id"]
    started = post(
        f"{API}/investigations",
        json={"repository_id": repository_id, "question": "Give an overview of this repository"},
        timeout=30,
    )
    assert started.status_code == 202
    session_id = started.json()["session_id"]
    _wait_investigation(session_id)
    first = get(f"{API}/investigations/{session_id}/trace", timeout=30).json()
    assert first["trace"]
    assert "content" not in first["trace"][0]["arguments"]
    added = post(
        f"{API}/investigations/{session_id}/messages",
        json={"question": "How does POST /users work?"},
        timeout=30,
    )
    assert added.status_code == 202
    _wait_investigation(session_id)
    second = get(f"{API}/investigations/{session_id}/trace", timeout=30).json()
    assert len(second["trace"]) > len(first["trace"])
    assert second["trace"][0]["argument_hash"]
    with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {ALICE}"}) as client:
        architecture = client.get(f"{API}/repositories/{repository_id}/architecture").json()
        trace = client.get(f"{API}/investigations/{session_id}/trace").json()
    assert architecture["status"] == "ready"
    assert trace["trace"]


def test_overview_and_file_use_stored_rows(imported):
    repository_id = imported["repository_id"]
    overview = get(f"{API}/repositories/{repository_id}/overview", timeout=30)
    assert overview.status_code == 200
    assert overview.json()["resolved_commit"]
    assert "workspace_path" not in overview.json()
    listed = get(f"{API}/repositories", timeout=30).json()
    assert any(item["repository_id"] == repository_id for item in listed["repositories"])
    opened = get(
        f"{API}/repositories/{repository_id}/file",
        params={"path": "app/main.py", "start_line": 1},
        timeout=30,
    )
    assert opened.status_code == 200
    assert "FastAPI" in opened.json()["content"]


def test_failed_analyze_releases_the_lock(imported):
    repository_id = imported["repository_id"]
    workspace = _workspace(repository_id)
    analysis_file = workspace.parent / f"{repository_id}.analysis.json"
    if analysis_file.exists():
        analysis_file.unlink()
    shutil.rmtree(workspace)
    store = redis.Redis.from_url(os.environ["REDIS_URL"])
    for key in store.scan_iter(f"*{repository_id}*"):
        store.delete(key)
    response = post(f"{API}/repositories/{repository_id}/analyze", timeout=30)
    assert response.status_code == 202
    job = _wait_job(repository_id, "analyze", "failed")
    assert job["error_code"]
    assert store.get(f"lock:analysis:{repository_id}") is None


def test_bob_cannot_read_alices_repository_or_trace(imported):
    repository_id = imported["repository_id"]
    missing = get(f"{API}/repositories/{repository_id}", token=BOB, timeout=30)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REPOSITORY_NOT_FOUND"
    started = post(
        f"{API}/investigations",
        json={"repository_id": repository_id, "question": "Give an overview of this repository"},
        timeout=30,
    )
    assert started.status_code == 202
    session_id = started.json()["session_id"]
    _wait_investigation(session_id)
    hidden = get(f"{API}/investigations/{session_id}/trace", token=BOB, timeout=30)
    assert hidden.status_code == 404


def test_cleanup_expires_the_row_and_removes_the_directory(imported):
    repository_id = imported["repository_id"]
    workspace = _workspace(repository_id)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "marker.txt").write_text("keep", encoding="utf-8")
    expired = expire_workspaces(0)
    assert repository_id in expired
    assert not workspace.exists()
    body = get(f"{API}/repositories/{repository_id}", timeout=30).json()
    assert body["status"] == "expired"


def test_import_rate_limit(fixture_repo):
    del fixture_repo
    limited = False
    prefix = uuid.uuid4()
    for index in range(12):
        response = post(
            f"{API}/repositories",
            json={"url": FIXTURE_URL},
            headers={"Idempotency-Key": f"rate-{prefix}-{index}"},
            timeout=30,
        )
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "RATE_LIMITED"
            limited = True
            break
    assert limited


def test_file_route_rejects_traversal(imported):
    repository_id = imported["repository_id"]
    response = get(
        f"{API}/repositories/{repository_id}/file",
        params={"path": "../../etc/passwd"},
        timeout=30,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PATH"


def test_fourth_analysis_job_is_a_quota(imported):
    repository_id = imported["repository_id"]
    limited = False
    for _ in range(6):
        response = post(f"{API}/repositories/{repository_id}/analyze", timeout=30)
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"
            assert response.json()["error"]["retryable"] is False
            limited = True
            break
        assert response.status_code == 202
        _wait_job(repository_id, "analyze", "succeeded")
    assert limited


def test_oversized_body_is_a_quota():
    response = post(f"{API}/repositories", content=b"x" * 1_000_001, timeout=30)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"
    assert response.json()["error"]["retryable"] is False


def test_injection_file_stays_content(fixture_repo):
    del fixture_repo
    source = Path(os.environ["INJECTION_SOURCE"])
    destination = Path(os.environ["INJECTION_DEST"])
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    _git(destination, "init")
    _git(destination, "add", ".")
    _git(destination, "commit", "-m", "init")
    key = f"inject-{uuid.uuid4()}"
    created = None
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        created = post(
            f"{API}/repositories",
            json={"url": "file:///fixtures/injection_repo"},
            headers={"Idempotency-Key": key},
            timeout=30,
        )
        if created.status_code in (200, 202):
            break
        assert created.status_code == 429
        time.sleep(2)
    assert created is not None and created.status_code in (200, 202)
    record = _wait_ready(created.json()["repository_id"], created.json()["job_id"])
    started = post(
        f"{API}/investigations",
        json={"repository_id": record["repository_id"], "question": "Read notes.txt"},
        timeout=30,
    )
    assert started.status_code == 202
    body = _wait_investigation(started.json()["session_id"])
    text = " ".join(item.get("text", "") for item in body["messages"])
    assert "content" in text.lower()
    bob = get(f"{API}/repositories/{record['repository_id']}", token=BOB, timeout=30)
    assert bob.status_code == 404


def _wait_investigation(session_id: str) -> dict:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        body = get(f"{API}/investigations/{session_id}", timeout=30).json()
        job = body.get("job") or {}
        if job.get("status") == "failed":
            pytest.fail(str(job))
        if job.get("status") == "succeeded":
            return body
        time.sleep(0.4)
    pytest.fail("investigation did not finish")


def _wait_ready(repository_id: str, job_id: str) -> dict:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        status = get(f"{API}/repositories/{repository_id}/status", timeout=30)
        if status.status_code == 200:
            job = status.json().get("job") or {}
            if job.get("id") == job_id and job.get("status") == "failed":
                pytest.fail(str(job))
        response = get(f"{API}/repositories/{repository_id}", timeout=30)
        if response.status_code == 200 and response.json()["status"] == "ready":
            return response.json()
        time.sleep(0.4)
    pytest.fail(f"{repository_id} did not become ready")


def _analyze(repository_id: str) -> dict:
    response = post(f"{API}/repositories/{repository_id}/analyze", timeout=30)
    assert response.status_code == 202
    return _wait_job(repository_id, "analyze", "succeeded")


def _wait_job(repository_id: str, kind: str, status: str) -> dict:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        body = get(f"{API}/repositories/{repository_id}/status", timeout=30).json()
        job = body.get("job") or {}
        if job.get("kind") == kind and job.get("status") == status:
            return job
        if job.get("kind") == kind and job.get("status") == "failed" and status != "failed":
            pytest.fail(str(job))
        time.sleep(0.4)
    pytest.fail(f"{kind} did not reach {status}")


def _clear_analysis_jobs(repository_id: str) -> None:
    """Earlier runs keep analysis jobs for the same repository id. This run starts at zero."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        connection.execute(
            "DELETE FROM jobs WHERE repository_id = %s AND kind = 'analyze'",
            (repository_id,),
        )


def _workspace(repository_id: str) -> Path:
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        row = connection.execute(
            "SELECT workspace_path FROM repositories WHERE repository_id = %s",
            (repository_id,),
        ).fetchone()
    return Path(row[0])


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
