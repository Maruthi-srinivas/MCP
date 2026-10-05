"""Nearest symbols for a short query. The result cites path and line."""

from analysis_mcp.analysis.artifact import ensure_artifact
from analysis_mcp.analysis.embed import embed_texts, ranked
from analysis_mcp.analysis.vectors import search
from analysis_mcp.logging import observed_tool


@observed_tool
def search_symbols(repository_id: str, query: str) -> dict:
    """Return the closest symbols for a query. Each match has a path, line, and snippet."""
    text = query.strip()
    artifact = ensure_artifact(repository_id)
    if not text:
        return {"repository_id": repository_id, "query": query, "matches": []}
    vector = embed_texts([text])[0]
    matches = search(repository_id, vector)
    if matches is None:
        matches = ranked(vector, artifact.get("embeddings") or [])
    return {"repository_id": repository_id, "query": query, "matches": matches}
