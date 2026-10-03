"""Shallow git clone and fetch. The GitHub token stays in the process environment."""

import os
import shutil
import subprocess
from pathlib import Path

from repository_mcp.config import Settings
from repository_mcp.errors import ToolFailure
from repository_mcp.workspace.ids import RepositoryTarget, is_commit_sha

_GIT = ["git", "-c", "safe.directory=*"]


def redact(text: str, token: str | None) -> str:
    """Remove a credential if git echoed it back."""
    if token and token in text:
        text = text.replace(token, "[redacted]")
    return text


def git_env(token: str | None) -> dict[str, str]:
    """Pass the token as an HTTP header for this command only. It is not stored in .git/config."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if token:
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token}"
    return env


def run_git(
    args: list[str],
    *,
    cwd: Path | None,
    env: dict[str, str],
    timeout: int,
    token: str | None,
) -> subprocess.CompletedProcess[str]:
    """Run one git command. The argument list must not contain the token."""
    try:
        completed = subprocess.run(
            [*_GIT, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolFailure("TOOL_TIMEOUT", "Git command exceeded the configured deadline.", True) from exc
    if completed.returncode != 0:
        raise _failure_from_git(completed.stderr, token)
    return completed


def sync_workspace(target: RepositoryTarget, ref: str | None, dest: Path, settings: Settings) -> str:
    """Clone or refresh dest and return the resolved commit SHA."""
    token = settings.github_token if target.kind == "github" else None
    env = git_env(token)
    timeout = settings.clone_timeout_seconds
    depth = str(settings.git_clone_depth)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if (dest / ".git").is_dir():
            _fetch_existing(target, ref, dest, env, timeout, token, depth)
        else:
            if dest.exists():
                shutil.rmtree(dest)
            _initial_clone(target, ref, dest, env, timeout, token, depth)
        completed = run_git(
            ["rev-parse", "HEAD"],
            cwd=dest,
            env=env,
            timeout=timeout,
            token=token,
        )
    except ToolFailure:
        if not (dest / ".git").is_dir() and dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        raise
    return completed.stdout.strip()


def _initial_clone(
    target: RepositoryTarget,
    ref: str | None,
    dest: Path,
    env: dict[str, str],
    timeout: int,
    token: str | None,
    depth: str,
) -> None:
    command = ["clone", "--depth", depth]
    if ref and not is_commit_sha(ref):
        command.extend(["--branch", ref])
    command.extend([target.clone_url, str(dest)])
    run_git(command, cwd=None, env=env, timeout=timeout, token=token)
    if ref and is_commit_sha(ref):
        _checkout_fetched(ref, dest, env, timeout, token, depth)


def _fetch_existing(
    target: RepositoryTarget,
    ref: str | None,
    dest: Path,
    env: dict[str, str],
    timeout: int,
    token: str | None,
    depth: str,
) -> None:
    run_git(
        ["remote", "set-url", "origin", target.clone_url],
        cwd=dest,
        env=env,
        timeout=timeout,
        token=token,
    )
    if ref and is_commit_sha(ref):
        _checkout_fetched(ref, dest, env, timeout, token, depth)
        return
    fetch_ref = ref or "HEAD"
    run_git(
        ["fetch", "--depth", depth, "origin", fetch_ref],
        cwd=dest,
        env=env,
        timeout=timeout,
        token=token,
    )
    run_git(
        ["checkout", "--detach", "FETCH_HEAD"],
        cwd=dest,
        env=env,
        timeout=timeout,
        token=token,
    )


def _checkout_fetched(
    ref: str,
    dest: Path,
    env: dict[str, str],
    timeout: int,
    token: str | None,
    depth: str,
) -> None:
    run_git(
        ["fetch", "--depth", depth, "origin", ref],
        cwd=dest,
        env=env,
        timeout=timeout,
        token=token,
    )
    run_git(
        ["checkout", "--detach", "FETCH_HEAD"],
        cwd=dest,
        env=env,
        timeout=timeout,
        token=token,
    )


def _failure_from_git(stderr: str, token: str | None) -> ToolFailure:
    message = redact(stderr, token).strip()
    lowered = message.lower()
    if "rate limit" in lowered or "http 429" in lowered or "too many requests" in lowered:
        return ToolFailure("GITHUB_RATE_LIMIT", "GitHub API rate limit reached.", True)
    if "not found" in lowered or "repository not found" in lowered or "authentication" in lowered:
        return ToolFailure("REPOSITORY_NOT_FOUND", "Repository is inaccessible or was not found.", False)
    summary = message.splitlines()[-1] if message else "Clone failed."
    if len(summary) > 300:
        summary = summary[:300]
    retryable = "could not resolve" in lowered or "timed out" in lowered or "connection" in lowered
    return ToolFailure("CLONE_FAILED", summary or "Clone failed.", retryable)
