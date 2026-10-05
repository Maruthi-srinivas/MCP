"""Architecture resources and analysis prompts."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from analysis_mcp.prompts import review_architecture, trace_api
from analysis_mcp.resources import read_uri
from analysis_mcp.server import mcp
from tests.conftest import save_record

FIXTURE = Path(__file__).parents[1] / "fixtures" / "service_app"
_TOOLS = ("search_code", "find_symbol", "read_file", "find_references", "detect_database_access")


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


def test_architecture_and_endpoints_resolve(service):
    architecture = json.loads(read_uri(f"repo://{service}/architecture"))
    assert architecture["commit_sha"] == "a" * 40
    assert any(edge.get("target") == "create_user" for edge in architecture["edges"])

    endpoints = json.loads(read_uri(f"repo://{service}/analysis/endpoints"))
    assert any(item["path"] == "/users" and item["method"] == "POST" for item in endpoints["endpoints"])

    missing = json.loads(read_uri("repo://repo_0000000000000000/architecture"))
    assert missing["error"]["code"] == "REPOSITORY_NOT_FOUND"


def test_prompts_are_listed_and_trace_api_names_tools_in_order():
    prompts = asyncio.run(mcp.list_prompts())
    names = sorted(prompt.name for prompt in prompts)
    assert names == ["review_architecture", "trace_api"]
    review = review_architecture("repo_x")
    assert "build_dependency_graph" in review
    assert "detect_api_endpoints" in review
    assert "detect_entrypoints" in review
    text = trace_api("repo_x", "item")
    positions = [text.find(name) for name in _TOOLS]
    assert positions == sorted(positions)
    assert all(position >= 0 for position in positions)
    assert text.find("search_symbols") < text.find("search_code")
    source = Path(__file__).parents[2].joinpath("src", "analysis_mcp", "prompts.py").read_text(encoding="utf-8")
    assert "/users" not in source
