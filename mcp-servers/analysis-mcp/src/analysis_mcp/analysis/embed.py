"""MiniLM vectors for symbol lines. The model is loaded from the image cache."""

import math
import os
from pathlib import Path

_MODEL = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one normalized vector per text. An empty input returns an empty list."""
    if not texts:
        return []
    model = _model()
    encoded = model.encode(texts, normalize_embeddings=True)
    return [[round(float(value), 6) for value in row] for row in encoded]


def line_snippet(root: Path, path: str, line_number: int) -> str:
    """The source line for a symbol, shortened so a search result stays small."""
    file_path = root / path
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return f"{path}:{line_number}"
    if line_number < 1 or line_number > len(lines):
        return f"{path}:{line_number}"
    return lines[line_number - 1].strip()[:240] or f"{path}:{line_number}"


def cosine(left: list[float], right: list[float]) -> float:
    """Dot product of two normalized vectors."""
    return sum(a * b for a, b in zip(left, right))


def ranked(query: list[float], rows: list[dict], limit: int = 10) -> list[dict]:
    """Highest cosine similarity first. The vector itself is not returned."""
    scored = []
    for row in rows:
        vector = row.get("vector") or []
        if not vector:
            continue
        score = cosine(query, vector)
        if math.isnan(score):
            continue
        scored.append(
            {
                "name": row["name"],
                "kind": row.get("kind") or "",
                "path": row["path"],
                "line": row.get("start_line") or row.get("line"),
                "snippet": row.get("snippet") or "",
                "score": round(score, 4),
            }
        )
    scored.sort(key=lambda item: (-item["score"], item["path"], item["line"], item["name"]))
    return scored[:limit]


def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(_MODEL_NAME)
    return _MODEL


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()
