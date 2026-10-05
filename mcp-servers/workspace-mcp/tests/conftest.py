import json
import os

import pytest

os.environ.setdefault("WRITE_ENABLED", "1")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "")
    return tmp_path


def save_record(repository_id: str, destination, sha: str) -> None:
    from investigator_shared.registry import registry_path

    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "repositories": {
                    repository_id: {
                        "repository_id": repository_id,
                        "url": "file:///fixtures/service_app",
                        "owner": "local",
                        "name": "service_app",
                        "ref": None,
                        "resolved_commit": sha,
                        "workspace_path": str(destination),
                        "status": "ready",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
