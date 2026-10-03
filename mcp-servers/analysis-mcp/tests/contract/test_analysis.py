"""Contract checks for the service_app fixture."""

import hashlib
import shutil
from pathlib import Path

import pytest

from analysis_mcp.tools.analyze_code import analyze_code
from analysis_mcp.tools.build_dependency_graph import build_dependency_graph
from analysis_mcp.tools.detect_api_endpoints import detect_api_endpoints
from analysis_mcp.tools.detect_database_access import detect_database_access
from analysis_mcp.tools.detect_external_services import detect_external_services
from analysis_mcp.tools.find_functions import find_functions
from tests.conftest import save_record

FIXTURE = Path(__file__).parents[1] / "fixtures" / "service_app"


def _repository_id() -> str:
    digest = hashlib.sha256(b"https://github.com/example/service\nHEAD").hexdigest()[:16]
    return f"repo_{digest}"


@pytest.fixture
def service(workspace):
    repository_id = _repository_id()
    destination = workspace / repository_id
    shutil.copytree(FIXTURE, destination)
    save_record(repository_id, destination, "a" * 40)
    return repository_id


def test_endpoints_graph_hints_and_warning(service):
    endpoints = detect_api_endpoints(service)
    match = [item for item in endpoints["endpoints"] if item["path"] == "/users"]
    assert match
    assert match[0]["method"] == "POST"
    assert match[0]["framework"] == "fastapi"
    assert match[0]["file"] == "app/main.py"
    assert match[0]["line"] >= 1

    graph = build_dependency_graph(service)
    assert any(
        edge["kind"] == "call" and edge["inferred"] is True and edge["target"] == "create_user"
        for edge in graph["edges"]
    )

    hints = detect_database_access(service)
    assert any(item["library"] == "sqlite3" and item["file"] == "app/users/service.py" for item in hints["hints"])

    services = detect_external_services(service)
    assert any(
        item["library"] == "httpx" and item.get("url") == "https://example.test/users" and item["inferred"] is False
        for item in services["services"]
    )

    report = analyze_code(service)
    assert report["counts"]["endpoints"] >= 1
    assert report["counts"]["functions"] >= 1
    assert any(item["path"] == "broken.py" and item["message"].startswith("Syntax error:") for item in report["warnings"])

    missing = find_functions(service, name="no_such_function")
    assert missing["functions"] == []
    assert missing["truncated"] is False


def test_unknown_repository(workspace):
    del workspace
    missing = analyze_code("repo_0000000000000000")
    assert missing["error"]["code"] == "REPOSITORY_NOT_FOUND"
    assert missing["error"]["retryable"] is False
