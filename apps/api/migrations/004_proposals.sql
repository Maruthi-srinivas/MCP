CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    session_id UUID REFERENCES investigation_sessions (id),
    caller_id TEXT,
    base_commit TEXT NOT NULL DEFAULT '',
    diff_text TEXT NOT NULL,
    diff_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_id UUID,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
