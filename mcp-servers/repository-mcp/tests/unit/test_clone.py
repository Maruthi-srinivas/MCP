import subprocess

from repository_mcp.workspace.clone import git_env, redact, run_git


def test_redact_removes_token():
    assert "super-secret-token" not in redact("auth super-secret-token failed", "super-secret-token")


def test_git_command_does_not_carry_the_token(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs["env"]

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_git(
        ["status"],
        cwd=None,
        env=git_env("super-secret-token"),
        timeout=5,
        token="super-secret-token",
    )
    assert "super-secret-token" not in " ".join(seen["command"])
    assert seen["env"]["GIT_CONFIG_VALUE_0"] == "Authorization: Bearer super-secret-token"
