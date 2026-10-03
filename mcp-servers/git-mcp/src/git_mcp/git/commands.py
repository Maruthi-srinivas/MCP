"""The only module that runs git. Tools call these functions; they never build a shell string."""

import os
import subprocess
from pathlib import Path

from investigator_shared.errors import ToolFailure
from investigator_shared.paths import relative_to_root, repository_root, resolve_inside

_GIT = ["git", "-c", "safe.directory=*"]
_PRETTY = "%H\x1f%an\x1f%aI\x1f%s"
_SEPARATOR = "\x1f"


def validate_ref(ref: str) -> str:
    """Reject values git could treat as a flag or a path escape."""
    if (
        not ref
        or ref.startswith("-")
        or ".." in ref
        or "//" in ref
        or any(character in ref for character in "\n\r\t :")
    ):
        raise ToolFailure("GIT_REF_NOT_FOUND", "Unknown git ref.", False)
    return ref


def head_sha(repository_id: str) -> str:
    root = repository_root(repository_id)
    completed = run_git(["rev-parse", "HEAD"], cwd=root)
    return completed.stdout.strip()


def status(repository_id: str) -> dict:
    root = repository_root(repository_id)
    sha = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    porcelain = run_git(["status", "--porcelain=v1", "-b"], cwd=root).stdout.splitlines()
    branch = "HEAD"
    entries: list[dict] = []
    for line in porcelain:
        if line.startswith("##"):
            branch = _branch_name(line)
            continue
        if len(line) < 4:
            continue
        entries.append({"status": line[:2].strip() or line[:2], "path": line[3:]})
    return {
        "repository_id": repository_id,
        "head_sha": sha,
        "branch": branch,
        "clean": not entries,
        "entries": entries,
    }


def branches(repository_id: str, limit: int) -> dict:
    root = repository_root(repository_id)
    completed = run_git(
        ["for-each-ref", "--format=%(refname)%00%(objectname)", "refs/heads", "refs/remotes"],
        cwd=root,
    )
    found: list[dict] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        refname, _, sha = line.partition("\0")
        if refname.startswith("refs/heads/"):
            found.append({"name": refname.removeprefix("refs/heads/"), "sha": sha, "kind": "local"})
        elif refname.startswith("refs/remotes/"):
            found.append({"name": refname.removeprefix("refs/remotes/"), "sha": sha, "kind": "remote"})
    found.sort(key=lambda item: (item["kind"], item["name"]))
    return {
        "repository_id": repository_id,
        "branches": found[:limit],
        "truncated": len(found) > limit,
    }


def commits(repository_id: str, ref: str, page: int, page_size: int) -> dict:
    root = repository_root(repository_id)
    checked = validate_ref(ref)
    resolved = _resolve(root, checked)
    skip = (page - 1) * page_size
    listed = _log(root, [checked, f"--skip={skip}", f"--max-count={page_size + 1}"])
    truncated = len(listed) > page_size
    return {
        "repository_id": repository_id,
        "ref": checked,
        "resolved_sha": resolved,
        "page": page,
        "page_size": page_size,
        "commits": listed[:page_size],
        "truncated": truncated,
    }


def commit(repository_id: str, ref: str) -> dict:
    root = repository_root(repository_id)
    checked = validate_ref(ref)
    completed = run_git(["show", "-s", f"--pretty=tformat:{_PRETTY}", checked], cwd=root)
    parsed = _parse_commit(completed.stdout.strip())
    if parsed is None:
        raise ToolFailure("GIT_REF_NOT_FOUND", "Unknown git ref.", False)
    return {"repository_id": repository_id, **parsed}


def diff(repository_id: str, base: str, head: str, max_lines: int) -> dict:
    root = repository_root(repository_id)
    base_sha = _resolve(root, validate_ref(base))
    head_sha = _resolve(root, validate_ref(head))
    patch = run_git(["diff", "--no-color", base_sha, head_sha], cwd=root).stdout
    lines = patch.splitlines()
    truncated = len(lines) > max_lines
    shown = "\n".join(lines[:max_lines])
    return {
        "repository_id": repository_id,
        "base": base,
        "head": head,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "patch": shown,
        "truncated": truncated,
    }


def file_history(repository_id: str, path: str, ref: str, page: int, page_size: int) -> dict:
    root = repository_root(repository_id)
    relative = _relative_file(root, path)
    checked = validate_ref(ref)
    resolved = _resolve(root, checked)
    skip = (page - 1) * page_size
    listed = _log(root, [checked, f"--skip={skip}", f"--max-count={page_size + 1}", "--", relative])
    truncated = len(listed) > page_size
    return {
        "repository_id": repository_id,
        "path": relative,
        "ref": checked,
        "resolved_sha": resolved,
        "page": page,
        "page_size": page_size,
        "commits": listed[:page_size],
        "truncated": truncated,
    }


def compare(repository_id: str, base: str, head: str, limit: int) -> dict:
    root = repository_root(repository_id)
    base_sha = _resolve(root, validate_ref(base))
    head_sha = _resolve(root, validate_ref(head))
    counts = run_git(["rev-list", "--left-right", "--count", f"{base_sha}...{head_sha}"], cwd=root)
    left, _, right = counts.stdout.strip().partition("\t")
    names = run_git(["diff", "--name-status", base_sha, head_sha], cwd=root).stdout.splitlines()
    changed = []
    for line in names:
        if not line.strip():
            continue
        status_code, _, file_path = line.partition("\t")
        changed.append({"status": status_code, "path": file_path})
    return {
        "repository_id": repository_id,
        "base": base,
        "head": head,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "behind": int(left or "0"),
        "ahead": int(right or "0"),
        "changed_paths": changed[:limit],
        "truncated": len(changed) > limit,
    }


def introduced_change(repository_id: str, path: str, line: int) -> dict:
    if line < 1:
        raise ToolFailure("INVALID_PATH", "Line numbers must start at 1.", False)
    root = repository_root(repository_id)
    relative = _relative_file(root, path)
    completed = run_git(
        ["log", "-L", f"{line},{line}:{relative}", "-n", "1", f"--pretty=tformat:{_PRETTY}"],
        cwd=root,
    )
    parsed = _first_commit(completed.stdout)
    if parsed is None:
        raise ToolFailure("GIT_REF_NOT_FOUND", "No commit contains that line.", False)
    return {"repository_id": repository_id, "path": relative, "line": line, **parsed}


def run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one read-only git command. GIT_OPTIONAL_LOCKS avoids index.lock on a read-only mount."""
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [*_GIT, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=_timeout(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolFailure("TOOL_TIMEOUT", "Git command exceeded the configured deadline.", True) from exc
    if completed.returncode != 0:
        raise _failure(completed.stderr)
    return completed


def _timeout() -> int:
    raw = os.environ.get("TOOL_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 30
    return int(raw)


def _resolve(root: Path, ref: str) -> str:
    completed = run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=root)
    return completed.stdout.strip()


def _log(root: Path, args: list[str]) -> list[dict]:
    completed = run_git(["log", f"--pretty=tformat:{_PRETTY}", *args], cwd=root)
    commits_found = []
    for line in completed.stdout.splitlines():
        parsed = _parse_commit(line.strip())
        if parsed is not None:
            commits_found.append(parsed)
    return commits_found


def _parse_commit(line: str) -> dict | None:
    parts = line.split(_SEPARATOR)
    if len(parts) < 4 or len(parts[0]) != 40:
        return None
    return {"sha": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]}


def _first_commit(text: str) -> dict | None:
    for line in text.splitlines():
        parsed = _parse_commit(line.strip())
        if parsed is not None:
            return parsed
    return None


def _relative_file(root: Path, path: str) -> str:
    resolved = resolve_inside(root, path)
    if resolved == root.resolve():
        raise ToolFailure("INVALID_PATH", "Path must name a file.", False)
    return relative_to_root(root, resolved)


def _branch_name(header: str) -> str:
    text = header.removeprefix("## ").split("...")[0].strip()
    if text.startswith("No commits") or text == "HEAD (no branch)":
        return "HEAD"
    return text or "HEAD"


def _failure(stderr: str) -> ToolFailure:
    lowered = stderr.lower()
    if (
        "unknown revision" in lowered
        or "bad revision" in lowered
        or "ambiguous argument" in lowered
        or "needed a single revision" in lowered
        or "bad object" in lowered
    ):
        return ToolFailure("GIT_REF_NOT_FOUND", "Unknown git ref.", False)
    if "not a git repository" in lowered:
        return ToolFailure("REPOSITORY_NOT_FOUND", "Workspace is not a git repository.", False)
    message = stderr.strip().splitlines()
    summary = message[-1] if message else "Git command failed."
    if len(summary) > 300:
        summary = summary[:300]
    return ToolFailure("INTERNAL_ERROR", summary, False)
