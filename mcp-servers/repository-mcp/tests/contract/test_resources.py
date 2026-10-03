"""Resource templates and prompts stay on the repository server."""

import asyncio
import json
import os
from pathlib import Path

from repository_mcp.prompts import explain_repository, explain_symbol, onboard_developer
from repository_mcp.resources import read_uri
from repository_mcp.server import mcp

SECRET_VALUE = "sk-resource-fixture-value"
PEM_BODY = "MIIRESOURCEPRIVATEBLOCK"
TOKEN_ENV = "ghp_resource_fixture_token"


def _body(uri: str) -> dict:
    return json.loads(read_uri(uri))


def test_metadata_structure_and_dependencies_resolve(seeded):
    metadata = _body(f"repo://{seeded}/metadata")
    assert metadata["repository_id"] == seeded
    assert metadata["resolved_commit"]
    assert "workspace_path" not in metadata

    structure = _body(f"repo://{seeded}/structure")
    assert structure["commit_sha"] == metadata["resolved_commit"]
    assert isinstance(structure["symbols"], list)
    assert isinstance(structure["python_files"], list)

    dependencies = _body(f"repo://{seeded}/dependencies")
    assert dependencies["commit_sha"] == metadata["resolved_commit"]
    assert isinstance(dependencies["dependencies"], list)


def test_file_traversal_is_rejected(seeded):
    escaped = _body(f"repo://{seeded}/file/../../etc/passwd")
    assert escaped["error"]["code"] == "INVALID_PATH"


def test_unknown_repository_is_an_error(workspace):
    del workspace
    missing = _body("repo://repo_0000000000000000/metadata")
    assert missing["error"]["code"] == "REPOSITORY_NOT_FOUND"


def test_secret_strings_are_absent(seeded, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN_ENV)
    root = Path(os.environ["WORKSPACE_ROOT"]) / seeded
    secret = root / "local_settings.py"
    secret.write_text(
        "\n".join(
            [
                f"API_TOKEN = {SECRET_VALUE}",
                "DB_SECRET = another-secret-value",
                "-----BEGIN PRIVATE KEY-----",
                PEM_BODY,
                "-----END PRIVATE KEY-----",
            ]
        ),
        encoding="utf-8",
    )
    body = read_uri(f"repo://{seeded}/file/local_settings.py")
    assert SECRET_VALUE not in body
    assert "another-secret-value" not in body
    assert PEM_BODY not in body
    assert TOKEN_ENV not in body
    assert "[redacted]" in body


def test_prompts_are_listed_and_name_tools():
    prompts = asyncio.run(mcp.list_prompts())
    names = sorted(prompt.name for prompt in prompts)
    assert names == ["explain_repository", "explain_symbol", "onboard_developer"]
    texts = {
        "explain_repository": explain_repository("repo_x"),
        "onboard_developer": onboard_developer("repo_x"),
        "explain_symbol": explain_symbol("repo_x", "create_user"),
    }
    assert "get_repository_info" in texts["explain_repository"]
    assert "detect_project_type" in texts["explain_repository"]
    assert "find_dependencies" in texts["explain_repository"]
    assert "list_directory" in texts["onboard_developer"]
    assert "detect_services" in texts["onboard_developer"]
    assert "read_file" in texts["onboard_developer"]
    assert "find_symbol" in texts["explain_symbol"]
    assert "find_references" in texts["explain_symbol"]
    assert "read_file" in texts["explain_symbol"]
    templates = asyncio.run(mcp.list_resource_templates())
    uris = {getattr(item, "uri_template", None) or getattr(item, "uriTemplate", None) for item in templates}
    assert "repo://{repository_id}/metadata" in uris
    assert "repo://{repository_id}/file/{file_path}" in uris
