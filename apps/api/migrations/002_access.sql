CREATE TABLE IF NOT EXISTS repository_access (
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    caller_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (repository_id, caller_id)
);

INSERT INTO repository_access (repository_id, caller_id)
SELECT repository_id, 'alice'
FROM repositories
ON CONFLICT (repository_id, caller_id) DO NOTHING;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS caller_id TEXT;

UPDATE jobs SET caller_id = 'alice' WHERE caller_id IS NULL AND kind <> 'cleanup';

ALTER TABLE investigation_sessions ADD COLUMN IF NOT EXISTS caller_id TEXT;

UPDATE investigation_sessions SET caller_id = 'alice' WHERE caller_id IS NULL;

ALTER TABLE tool_calls ADD COLUMN IF NOT EXISTS argument_hash TEXT NOT NULL DEFAULT '';

DROP INDEX IF EXISTS repositories_idempotency_key;

DROP INDEX IF EXISTS jobs_idempotency_key;

CREATE UNIQUE INDEX IF NOT EXISTS jobs_caller_idempotency
    ON jobs (caller_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND caller_id IS NOT NULL;
