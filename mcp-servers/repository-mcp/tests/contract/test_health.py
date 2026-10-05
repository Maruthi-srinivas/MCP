from starlette.testclient import TestClient

from repository_mcp.server import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        metrics = client.get("/metrics")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "repository-mcp"}
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["service"] == "repository-mcp"
    assert body["counters"]["github_http_calls"] == 0
