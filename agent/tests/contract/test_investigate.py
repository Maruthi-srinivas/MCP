"""Contract tests for the investigation loop. No OpenAI calls."""

import asyncio
from pathlib import Path

from starlette.testclient import TestClient

from agent_app.config import Settings
from agent_app.server import app, investigate
from tests.fake_mcp import COMMIT, FakeMcp
from tests.fake_model import ScriptedModel

ROUTE_QUESTION = "How does POST /users work?"


def _settings(**overrides) -> Settings:
    values = dict(
        host="127.0.0.1",
        port=8003,
        openai_api_key="",
        openai_model="gpt-4o-mini",
        test_model="scripted",
        repository_mcp_url="http://repository-mcp:8000/mcp",
        git_mcp_url="http://git-mcp:8001/mcp",
        analysis_mcp_url="http://analysis-mcp:8002/mcp",
        workspace_mcp_url="http://workspace-mcp:8005/mcp",
        max_steps=8,
        max_tool_calls=12,
        max_tool_output_chars=4000,
        timeout_seconds=60,
        max_retries=2,
    )
    values.update(overrides)
    return Settings(**values)


def test_comment_question_only_proposes():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {
                "repository_id": "repo_service",
                "session_id": "22222222-2222-2222-2222-222222222222",
                "question": "Add the comment reviewed to app/main.py",
            },
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [step["tool"] for step in result["trace"]] == ["propose_patch"]
    assert [name for name, _args in hub.calls] == ["propose_patch"]
    assert hub.calls[0][1]["session_id"] == "22222222-2222-2222-2222-222222222222"
    assert "diff" not in result["trace"][0]["arguments"]
    assert result["trace"][0]["arguments"]["proposal_id"] == "11111111-1111-1111-1111-111111111111"


def test_scripted_model_has_no_route_literal():
    source = Path(__file__).parents[1].joinpath("fake_model.py").read_text(encoding="utf-8")
    assert "/users" not in source


def test_route_question_follows_the_tool_sequence():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": ROUTE_QUESTION},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [step["tool"] for step in result["trace"]] == [
        "search_code",
        "find_symbol",
        "read_file",
        "find_references",
        "detect_database_access",
    ]
    assert result["stopped_reason"] == "answered"
    high = [item for item in result["evidence"] if item["confidence"] == "high"]
    assert high
    assert high[0]["commit_sha"] == COMMIT
    assert high[0]["file"]
    assert "content" not in result["trace"][2]["arguments"]


def test_overview_runs_independent_reads_together():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": "Give an overview of this repository"},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [name for name, _args in hub.calls] == [
        "get_repository_info",
        "detect_project_type",
        "find_dependencies",
    ]
    assert hub.max_inflight >= 3
    assert result["stopped_reason"] == "answered"


def test_missing_file_states_uncertainty_without_evidence():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": "Where is the missing file notes-missing.txt?"},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert result["trace"][0]["status"] == "FILE_NOT_FOUND"
    assert result["evidence"] == []
    assert "unknown" in result["answer"].lower()
    assert [name for name, _args in hub.calls] == ["read_file"]


def test_retryable_error_is_retried_and_other_errors_are_not():
    hub = FakeMcp()
    hub.queued["search_code"] = [
        {"error": {"code": "TOOL_TIMEOUT", "message": "slow", "retryable": True}},
    ]
    asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": ROUTE_QUESTION},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    search_calls = [name for name, _args in hub.calls if name == "search_code"]
    assert search_calls == ["search_code", "search_code"]

    missing = FakeMcp()
    asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": "Where is the missing file notes-missing.txt?"},
            hub=missing,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [name for name, _args in missing.calls] == ["read_file"]


class _AlwaysTools:
    async def decide(self, question: str, repository_id: str, observations: list[dict], tool_names: list[str]) -> dict:
        del question, observations, tool_names
        return {"tool_calls": [{"name": "get_commits", "arguments": {"repository_id": repository_id}}]}


def test_step_limit_stops_the_loop():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": "keep going"},
            hub=hub,
            model=_AlwaysTools(),
            settings=_settings(max_steps=2),
        )
    )
    assert result["stopped_reason"] == "max_steps"
    assert len(result["trace"]) == 2
    assert "step limit" in result["answer"]


def test_timeout_stops_before_tools():
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": ROUTE_QUESTION},
            hub=FakeMcp(),
            model=ScriptedModel(),
            settings=_settings(timeout_seconds=0),
        )
    )
    assert result["stopped_reason"] == "timeout"
    assert result["trace"] == []


def test_url_clones_before_the_loop():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"url": "https://github.com/example/service", "question": "Give an overview of this repository"},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert hub.calls[0][0] == "clone_repository"
    assert result["trace"][0]["tool"] == "clone_repository"
    assert result["stopped_reason"] == "answered"


def test_health_stays_up_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_TEST_MODEL", raising=False)
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["service"] == "agent"
    assert "counters" in metrics.json()
    body = client.post("/investigate", json={"repository_id": "repo_service", "question": "hello"})
    assert body.json()["stopped_reason"] == "configuration"
    assert body.json()["trace"] == []


def test_unknown_prompt_makes_no_tool_calls():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "prompt": "no_such_prompt"},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert hub.calls == []
    assert result["trace"] == []
    assert result["stopped_reason"] == "answered"
    assert "not found" in result["answer"]


PROMPT_NAMES = (
    "explain_repository",
    "explain_symbol",
    "investigate_change",
    "onboard_developer",
    "review_architecture",
    "trace_api",
)


def test_scripted_hub_prompt_stays_inside_the_catalog():
    names = {item["name"] for item in asyncio.run(FakeMcp().list_prompts())}
    assert names == {"trace_api"}
    assert names <= set(PROMPT_NAMES)


def test_trace_api_prompt_runs_the_five_tools():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {
                "repository_id": "repo_service",
                "prompt": "trace_api",
                "arguments": {"endpoint": "/users"},
            },
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [step["tool"] for step in result["trace"]] == [
        "search_code",
        "find_symbol",
        "read_file",
        "find_references",
        "detect_database_access",
    ]
    assert result["stopped_reason"] == "answered"


def test_express_question_searches_then_reads_the_route_file():
    hub = FakeMcp()
    result = asyncio.run(
        investigate(
            {
                "repository_id": "repo_service",
                "question": "How does the Express /notes route reach the database?",
            },
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [step["tool"] for step in result["trace"]] == ["search_symbols", "read_file"]
    assert result["trace"][1]["arguments"]["path"] == "app.js"
    assert "app.js" in result["answer"]
    assert result["stopped_reason"] == "answered"


def test_injection_file_is_content_and_there_is_no_shell():
    hub = FakeMcp()
    names = {item["name"] for item in asyncio.run(hub.list_tools())}
    assert "shell" not in names
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": "Read notes.txt"},
            hub=hub,
            model=ScriptedModel(),
            settings=_settings(),
        )
    )
    assert [step["tool"] for step in result["trace"]] == ["read_file"]
    assert "content" in result["answer"].lower()
    assert result["trace"][0]["argument_hash"]


def test_tool_cap_stops_the_loop():
    result = asyncio.run(
        investigate(
            {"repository_id": "repo_service", "question": ROUTE_QUESTION},
            hub=FakeMcp(),
            model=ScriptedModel(),
            settings=_settings(max_tool_calls=1),
        )
    )
    assert result["stopped_reason"] == "max_tool_calls"
