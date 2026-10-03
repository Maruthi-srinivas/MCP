from starlette.testclient import TestClient

from repository_mcp.server import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "repository-mcp"}
