CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repositories (
    repository_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    ref TEXT,
    resolved_commit TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS repositories_idempotency_key
    ON repositories (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS repository_files (
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    language TEXT NOT NULL,
    PRIMARY KEY (repository_id, path)
);

CREATE TABLE IF NOT EXISTS symbols (
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    PRIMARY KEY (repository_id, path, name, kind, start_line)
);

CREATE TABLE IF NOT EXISTS dependencies (
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (repository_id, name, source)
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    repository_id TEXT,
    idempotency_key TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency_key
    ON jobs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs (status, created_at);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    commit_sha TEXT NOT NULL,
    analyzer_version TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis_artifacts (
    run_id UUID PRIMARY KEY REFERENCES analysis_runs (id),
    body JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_sessions (
    id UUID PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES investigation_sessions (id),
    position INTEGER NOT NULL,
    server TEXT NOT NULL,
    tool TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    arguments JSONB NOT NULL
);
