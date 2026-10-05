"""Runtime settings. Read from the environment on each call so tests can override them."""

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
    database_url: str
    redis_url: str
    workspace_root: str
    repository_mcp_url: str
    git_mcp_url: str
    analysis_mcp_url: str
    workspace_mcp_url: str
    agent_url: str
    imports_per_minute: int
    analyses_per_minute: int
    workspace_ttl_seconds: int
    cache_ttl_seconds: int
    max_file_rows: int
    migrations_dir: str
    alice_token: str
    bob_token: str
    max_concurrent_imports: int
    max_analysis_jobs: int
    max_body_bytes: int
    analyzer_version: str


def get_settings() -> Settings:
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_int_env("PORT", 8004),
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://investigator:investigator@postgres:5432/investigator",
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        workspace_root=os.environ.get("WORKSPACE_ROOT", "/workspaces"),
        repository_mcp_url=os.environ.get("REPOSITORY_MCP_URL", "http://repository-mcp:8000/mcp"),
        git_mcp_url=os.environ.get("GIT_MCP_URL", "http://git-mcp:8001/mcp"),
        analysis_mcp_url=os.environ.get("ANALYSIS_MCP_URL", "http://analysis-mcp:8002/mcp"),
        workspace_mcp_url=os.environ.get("WORKSPACE_MCP_URL", "http://workspace-mcp:8005/mcp"),
        agent_url=os.environ.get("AGENT_URL", "http://agent:8003"),
        imports_per_minute=_int_env("IMPORTS_PER_MINUTE", 10),
        analyses_per_minute=_int_env("ANALYSES_PER_MINUTE", 5),
        workspace_ttl_seconds=_int_env("WORKSPACE_TTL_SECONDS", 7 * 24 * 60 * 60),
        cache_ttl_seconds=_int_env("CACHE_TTL_SECONDS", 3600),
        max_file_rows=_int_env("MAX_FILE_ROWS", 2000),
        migrations_dir=os.environ.get("MIGRATIONS_DIR", "/app/migrations"),
        alice_token=os.environ.get("ALICE_TOKEN", "alice-local-token"),
        bob_token=os.environ.get("BOB_TOKEN", "bob-local-token"),
        max_concurrent_imports=_int_env("MAX_CONCURRENT_IMPORTS", 2),
        max_analysis_jobs=_int_env("MAX_ANALYSIS_JOBS", 3),
        max_body_bytes=_int_env("MAX_BODY_BYTES", 1_000_000),
        analyzer_version=os.environ.get("ANALYZER_VERSION", "0.5.0"),
    )
