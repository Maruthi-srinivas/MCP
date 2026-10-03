"""Python AST index. One file at a time, with a hard stop at the configured caps."""

import ast
import os
from pathlib import Path

from repository_mcp.config import Settings

ANALYZER_VERSION = "0.2.0"
_SKIP_DIRECTORIES = {".git", "__pycache__", ".venv", "venv", "node_modules"}
_SOURCE_SUFFIXES = {
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
}


def build_index(root: Path, commit_sha: str, settings: Settings, started: float) -> dict:
    """Walk root and return a stable index. Parser failures become warnings."""
    files = _list_files(root)
    warnings: list[dict] = []
    languages: set[str] = set()
    other_source = 0
    for path in files:
        language = _SOURCE_SUFFIXES.get(path.suffix.lower())
        if language is None:
            continue
        languages.add(language)
        other_source += 1
        if other_source <= 50:
            warnings.append(
                {
                    "path": _relative(root, path),
                    "message": f"Skipped {language} file. Structural tools read Python only.",
                }
            )
    if other_source > 50:
        warnings.append({"path": ".", "message": "Further non-Python source files were not listed."})

    python_files = [path for path in files if path.suffix.lower() == ".py"]
    truncated = False
    if python_files:
        languages.add("Python")
    if len(python_files) > settings.max_python_files:
        truncated = True
        warnings.append(
            {
                "path": ".",
                "message": f"Indexed the first {settings.max_python_files} Python files.",
            }
        )
        python_files = python_files[: settings.max_python_files]

    symbols: list[dict] = []
    imports: list[dict] = []
    indexed_paths: list[str] = []
    deadline = started + settings.index_timeout_seconds
    for path in python_files:
        if _expired(deadline):
            truncated = True
            warnings.append({"path": ".", "message": "Index stopped after the time limit."})
            break
        relative = _relative(root, path)
        size = path.stat().st_size
        if size > settings.max_file_bytes:
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
        indexed_paths.append(relative)
        file_symbols, file_imports = _read_tree(tree, relative)
        for symbol in file_symbols:
            if len(symbols) >= settings.max_symbols:
                truncated = True
                warnings.append({"path": relative, "message": "Symbol cap reached. Later definitions were not indexed."})
                break
            symbols.append(symbol)
        else:
            imports.extend(file_imports)
            continue
        break

    symbols.sort(key=lambda item: (item["path"], item["start_line"], item["name"], item["kind"]))
    imports.sort(key=lambda item: (item["path"], item["line"], item["module"] or "", tuple(item["names"])))
    warnings.sort(key=lambda item: (item["path"], item["message"]))
    return {
        "analyzer_version": ANALYZER_VERSION,
        "commit_sha": commit_sha,
        "symbols": symbols,
        "imports": imports,
        "warnings": warnings,
        "python_files": sorted(indexed_paths),
        "languages": sorted(languages),
        "truncated": truncated,
    }


def _list_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SKIP_DIRECTORIES and not name.startswith("."))
        current = Path(directory)
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                continue
            found.append(path)
    return found


def _read_tree(tree: ast.AST, relative: str) -> tuple[list[dict], list[dict]]:
    symbols: list[dict] = []
    imports: list[dict] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._class_depth = 0
            self._function_depth = 0

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            symbols.append(_symbol(node.name, "class", relative, node))
            self._class_depth += 1
            self.generic_visit(node)
            self._class_depth -= 1

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            kind = "method" if self._class_depth and self._function_depth == 0 else "function"
            symbols.append(_symbol(node.name, kind, relative, node))
            self._function_depth += 1
            self.generic_visit(node)
            self._function_depth -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            kind = "method" if self._class_depth and self._function_depth == 0 else "async_function"
            symbols.append(_symbol(node.name, kind, relative, node))
            self._function_depth += 1
            self.generic_visit(node)
            self._function_depth -= 1

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                imports.append(
                    {
                        "path": relative,
                        "module": alias.name,
                        "names": [alias.name.split(".")[0]],
                        "line": node.lineno,
                    }
                )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            names = [alias.name for alias in node.names if alias.name != "*"]
            if not names:
                return
            imports.append(
                {
                    "path": relative,
                    "module": node.module,
                    "names": names,
                    "line": node.lineno,
                }
            )

    Visitor().visit(tree)
    return symbols, imports


def _symbol(name: str, kind: str, relative: str, node: ast.AST) -> dict:
    return {
        "name": name,
        "kind": kind,
        "path": relative,
        "start_line": node.lineno,
        "end_line": getattr(node, "end_lineno", node.lineno) or node.lineno,
    }


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _expired(deadline: float) -> bool:
    import time

    return time.monotonic() >= deadline
