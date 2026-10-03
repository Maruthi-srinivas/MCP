"""Git helpers for tests. Flags are passed with -c so no git config file is written."""

import subprocess
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "safe.directory=*",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
