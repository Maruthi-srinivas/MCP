"""Read Python dependency manifests. Comments and pip options are ignored."""

import re
import tomllib
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_VERSION = re.compile(r"(?:==|~=|>=|<=|!=|>|<)\s*([^,;\s\[]+)")


def find_manifest_dependencies(root: Path) -> tuple[list[dict], list[dict]]:
    """Return dependencies and warnings. A missing manifest is an empty list."""
    dependencies: list[dict] = []
    warnings: list[dict] = []
    for path in _manifests(root):
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        if path.name == "pyproject.toml":
            dependencies.extend(_read_pyproject(path, relative, warnings))
        else:
            dependencies.extend(_read_requirements(path, relative))
    dependencies.sort(key=lambda item: (item["source_file"], item["name"], item["version"] or ""))
    return dependencies, warnings


def parse_requirement(text: str) -> dict | None:
    """Parse one requirement. Return None for comments, flags, and includes."""
    line = text.split("#", 1)[0].strip()
    if not line or line.startswith("-") or line.startswith("."):
        return None
    name_match = _NAME.match(line)
    if name_match is None:
        return None
    version_match = _VERSION.search(line)
    return {
        "name": name_match.group(0),
        "version": version_match.group(1) if version_match else None,
    }


def _manifests(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        name = path.name
        if name == "pyproject.toml" or name == "requirements.txt" or (
            name.startswith("requirements-") and name.endswith(".txt")
        ):
            found.append(path)
    return sorted(found)


def _read_requirements(path: Path, relative: str) -> list[dict]:
    dependencies = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = parse_requirement(line)
        if parsed is None:
            continue
        parsed["source_file"] = relative
        dependencies.append(parsed)
    return dependencies


def _read_pyproject(path: Path, relative: str, warnings: list[dict]) -> list[dict]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        warnings.append({"path": relative, "message": "Could not parse pyproject.toml."})
        return []
    raw = data.get("project", {}).get("dependencies", [])
    if not isinstance(raw, list):
        return []
    dependencies = []
    for item in raw:
        if not isinstance(item, str):
            continue
        parsed = parse_requirement(item)
        if parsed is None:
            continue
        parsed["source_file"] = relative
        dependencies.append(parsed)
    return dependencies
