"""Copy symbol vectors into Postgres. The analysis JSON remains the source of truth."""

import psycopg

from analysis_mcp.analysis.embed import database_url


def store(repository_id: str, rows: list[dict]) -> None:
    """Replace this repository's embedding rows. No database URL means the JSON file is enough."""
    url = database_url()
    if not url:
        return
    with psycopg.connect(url) as connection:
        with connection.transaction():
            connection.execute("DELETE FROM symbol_embeddings WHERE repository_id = %s", (repository_id,))
            for row in rows:
                literal = "[" + ",".join(f"{value:.6f}" for value in row["vector"]) + "]"
                connection.execute(
                    """
                    INSERT INTO symbol_embeddings
                        (repository_id, path, name, kind, start_line, snippet, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        repository_id,
                        row["path"],
                        row["name"],
                        row.get("kind") or "",
                        int(row["start_line"]),
                        row.get("snippet") or "",
                        literal,
                    ),
                )


def search(repository_id: str, query_vector: list[float], limit: int = 10) -> list[dict] | None:
    """Nearest rows, or None when this process has no database URL."""
    url = database_url()
    if not url:
        return None
    literal = "[" + ",".join(f"{value:.6f}" for value in query_vector) + "]"
    with psycopg.connect(url) as connection:
        found = connection.execute(
            """
            SELECT name, kind, path, start_line, snippet,
                   1 - (embedding <=> %s::vector) AS score
            FROM symbol_embeddings
            WHERE repository_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, repository_id, literal, limit),
        ).fetchall()
    rows = []
    for row in found:
        rows.append(
            {
                "name": row[0],
                "kind": row[1],
                "path": row[2],
                "line": row[3],
                "snippet": row[4],
                "score": round(float(row[5]), 4),
            }
        )
    return rows
