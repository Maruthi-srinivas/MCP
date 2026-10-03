"""Detect language and a few frameworks from filenames and imports. No LLM."""

from pathlib import Path


def detect(index: dict, root: Path) -> dict:
    """Return sorted languages and frameworks for one index."""
    modules = {(item.get("module") or "") for item in index.get("imports", [])}
    frameworks: list[str] = []
    if _imports_prefix(modules, "fastapi"):
        frameworks.append("FastAPI")
    if _imports_prefix(modules, "flask"):
        frameworks.append("Flask")
    if _imports_prefix(modules, "django") or (root / "manage.py").is_file():
        frameworks.append("Django")
    return {
        "languages": list(index.get("languages", [])),
        "frameworks": frameworks,
    }


def _imports_prefix(modules: set[str], prefix: str) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for module in modules)
