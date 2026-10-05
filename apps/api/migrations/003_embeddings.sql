CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS symbol_embeddings (
    repository_id TEXT NOT NULL REFERENCES repositories (repository_id),
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    snippet TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    PRIMARY KEY (repository_id, path, name, kind, start_line)
);
