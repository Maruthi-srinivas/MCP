"""Express and Java fixtures. Python service_app stays in test_analysis.py."""

import hashlib
import shutil
from pathlib import Path

import pytest

from analysis_mcp.tools.build_dependency_graph import build_dependency_graph
from analysis_mcp.tools.detect_api_endpoints import detect_api_endpoints
from analysis_mcp.tools.find_classes import find_classes
from analysis_mcp.tools.find_functions import find_functions
from analysis_mcp.tools.find_imports import find_imports
from analysis_mcp.tools.search_symbols import search_symbols
from tests.conftest import save_record

EXPRESS = Path(__file__).parents[1] / "fixtures" / "express_app"
JAVA = Path(__file__).parents[1] / "fixtures" / "java_app"


def _repository_id(label: str) -> str:
    digest = hashlib.sha256(f"https://github.com/example/{label}\nHEAD".encode()).hexdigest()[:16]
    return f"repo_{digest}"


def _seed(workspace: Path, fixture: Path, label: str) -> str:
    repository_id = _repository_id(label)
    destination = workspace / repository_id
    shutil.copytree(fixture, destination)
    save_record(repository_id, destination, "b" * 40)
    return repository_id


@pytest.fixture
def express(workspace):
    return _seed(workspace, EXPRESS, "express")


@pytest.fixture
def java_app(workspace):
    return _seed(workspace, JAVA, "java")


def test_express_route_import_and_same_file_call(express):
    endpoints = detect_api_endpoints(express)
    match = [item for item in endpoints["endpoints"] if item["path"] == "/notes"]
    assert match
    assert match[0]["method"] == "GET"
    assert match[0]["framework"] == "express"
    assert match[0]["file"] == "app.js"
    assert match[0]["line"] >= 1

    imports = find_imports(express, name="express")
    assert any(item["path"] == "package.json" for item in imports["imports"])

    graph = build_dependency_graph(express)
    assert any(edge["kind"] == "import" and edge["target_path"] == "db.js" for edge in graph["edges"])
    assert any(
        edge["kind"] == "call" and edge["target"] == "reachDatabase" and edge["path"] == "app.js"
        for edge in graph["edges"]
    )

    functions = find_functions(express, name="noteTitle")
    assert functions["functions"]
    assert functions["functions"][0]["path"] == "notes.ts"

    report_imports = find_imports(express, name="./db")
    assert any(item["module"] == "./db" for item in report_imports["imports"])

    found = search_symbols(express, "reachDatabase")
    assert found["matches"]
    assert found["matches"][0]["path"] == "app.js"
    assert found["matches"][0]["line"] >= 1
    assert "vector" not in found["matches"][0]


def test_go_file_is_skipped(express):
    from analysis_mcp.tools.analyze_code import analyze_code

    report = analyze_code(express)
    assert any(item["path"] == "main.go" and item["message"].startswith("Skipped Go file") for item in report["warnings"])


def test_java_class_resolves_and_pom_is_labeled(java_app):
    classes = find_classes(java_app, name="Note")
    assert classes["classes"]
    assert classes["classes"][0]["path"] == "src/main/java/app/Note.java"

    imports = find_imports(java_app, name="notes-lib")
    assert any(item["path"] == "pom.xml" and "notes-lib" in item["names"] for item in imports["imports"])

    graph = build_dependency_graph(java_app)
    assert any(edge["kind"] == "import" and edge["target_path"].endswith("Store.java") for edge in graph["edges"])
