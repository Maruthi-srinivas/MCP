"""Walk a checkout and parse Python files. One syntax error does not stop the run."""

import ast
import os
import time
from pathlib import Path

from investigator_shared.errors import ToolFailure

from analysis_mcp.config import Settings

_SKIP_DIRECTORIES = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def list_python_files(root: Path) -> list[Path]:
    """Return Python files in a stable order, skipping vendor and hidden directories."""
    found: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SKIP_DIRECTORIES and not name.startswith("."))
        current = Path(directory)
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = current / name
            if path.is_symlink():
                continue
            found.append(path)
    return found


def parse_sources(root: Path, settings: Settings, started: float) -> tuple[list[tuple[str, ast.AST]], list[dict], bool]:
    """Parse up to the file cap. Returns trees, warnings, and whether the file list was cut."""
    files = list_python_files(root)
    warnings: list[dict] = []
    truncated = False
    if len(files) > settings.max_python_files:
        truncated = True
        warnings.append({"path": ".", "message": f"Analyzed the first {settings.max_python_files} Python files."})
        files = files[: settings.max_python_files]

    parsed: list[tuple[str, ast.AST]] = []
    deadline = started + settings.analysis_timeout_seconds
    for path in files:
        if time.monotonic() >= deadline:
            raise ToolFailure("ANALYSIS_TIMEOUT", "Analysis exceeded the configured deadline.", True)
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        if path.stat().st_size > settings.max_file_bytes:
            warnings.append({"path": relative, "message": "Skipped because the file exceeds the size limit."})
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append({"path": relative, "message": "Skipped because the file is not UTF-8 text."})
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            warnings.append({"path": relative, "message": f"Syntax error: {exc.msg}"})
            continue
        parsed.append((relative, tree))
    return parsed, warnings, truncated
