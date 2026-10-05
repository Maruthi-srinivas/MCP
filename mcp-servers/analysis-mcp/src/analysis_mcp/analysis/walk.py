"""Walk a checkout and parse source files. One syntax error does not stop the run."""

import ast
import os
import time
from pathlib import Path

from investigator_shared.errors import ToolFailure

from analysis_mcp.config import Settings
from analysis_mcp.languages import java, javascript, typescript

_SKIP_DIRECTORIES = {".git", "__pycache__", ".venv", "venv", "node_modules"}
_SCRIPT_SUFFIXES = {".js": javascript, ".ts": typescript, ".tsx": typescript}
_GO_WARNING = "Skipped Go file. Structural tools read Python only."


def list_python_files(root: Path) -> list[Path]:
    """Return source files in a stable order, skipping vendor and hidden directories."""
    found: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SKIP_DIRECTORIES and not name.startswith("."))
        current = Path(directory)
        for name in sorted(filenames):
            suffix = Path(name).suffix.lower()
            if suffix not in {".py", ".js", ".ts", ".tsx", ".java", ".go"}:
                continue
            path = current / name
            if path.is_symlink():
                continue
            found.append(path)
    return found


def parse_sources(root: Path, settings: Settings, started: float) -> tuple[list[tuple[str, ast.AST]], dict, list[dict], bool]:
    """Parse up to the file cap. Returns Python trees, other-language rows, warnings, and a cut flag."""
    files = list_python_files(root)
    warnings: list[dict] = []
    truncated = False
    python_files = [path for path in files if path.suffix.lower() == ".py"]
    other_files = [path for path in files if path.suffix.lower() != ".py"]
    if len(python_files) > settings.max_python_files:
        truncated = True
        warnings.append({"path": ".", "message": f"Analyzed the first {settings.max_python_files} Python files."})
        python_files = python_files[: settings.max_python_files]
    if len(other_files) > settings.max_python_files:
        truncated = True
        warnings.append({"path": ".", "message": f"Analyzed the first {settings.max_python_files} non-Python source files."})
        other_files = other_files[: settings.max_python_files]
    files = python_files + other_files

    parsed: list[tuple[str, ast.AST]] = []
    extra = {"functions": [], "classes": [], "imports": [], "endpoints": [], "calls": []}
    deadline = started + settings.analysis_timeout_seconds
    for path in files:
        if time.monotonic() >= deadline:
            raise ToolFailure("ANALYSIS_TIMEOUT", "Analysis exceeded the configured deadline.", True)
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        suffix = path.suffix.lower()
        if suffix == ".go":
            warnings.append({"path": relative, "message": _GO_WARNING})
            continue
        if path.stat().st_size > settings.max_file_bytes:
            warnings.append({"path": relative, "message": "Skipped because the file exceeds the size limit."})
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append({"path": relative, "message": "Skipped because the file is not UTF-8 text."})
            continue
        if suffix == ".py":
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:
                warnings.append({"path": relative, "message": f"Syntax error: {exc.msg}"})
                continue
            parsed.append((relative, tree))
            continue
        if suffix == ".java":
            _merge(extra, java.collect(source, relative))
            continue
        collector = _SCRIPT_SUFFIXES.get(suffix)
        if collector is not None:
            _merge(extra, collector.collect(source, relative))
    extra["imports"].extend(javascript.collect_manifest(root))
    extra["imports"].extend(java.collect_manifest(root))
    return parsed, extra, warnings, truncated


def _merge(extra: dict, found: dict) -> None:
    for key in extra:
        extra[key].extend(found.get(key) or [])
