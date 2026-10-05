"""Runtime settings. The API key is read here and never logged."""

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    openai_api_key: str
    openai_model: str
    test_model: str
    repository_mcp_url: str
    git_mcp_url: str
    analysis_mcp_url: str
    workspace_mcp_url: str
    max_steps: int
    max_tool_calls: int
    max_tool_output_chars: int
    timeout_seconds: int
    max_retries: int


def get_settings() -> Settings:
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8003),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        test_model=os.environ.get("AGENT_TEST_MODEL", "").strip(),
        repository_mcp_url=os.environ.get("REPOSITORY_MCP_URL", "http://repository-mcp:8000/mcp"),
        git_mcp_url=os.environ.get("GIT_MCP_URL", "http://git-mcp:8001/mcp"),
        analysis_mcp_url=os.environ.get("ANALYSIS_MCP_URL", "http://analysis-mcp:8002/mcp"),
        workspace_mcp_url=os.environ.get("WORKSPACE_MCP_URL", "http://workspace-mcp:8005/mcp"),
        max_steps=_int_env("MAX_STEPS", 8),
        max_tool_calls=_int_env("MAX_TOOL_CALLS", 12),
        max_tool_output_chars=_int_env("MAX_TOOL_OUTPUT_CHARS", 4000),
        timeout_seconds=_int_env("AGENT_TIMEOUT_SECONDS", 60),
        max_retries=_int_env("MAX_RETRIES", 2),
    )


def model_ready(settings: Settings) -> bool:
    """A real investigation needs a key. The scripted test model does not."""
    return bool(settings.openai_api_key) or settings.test_model == "scripted"
