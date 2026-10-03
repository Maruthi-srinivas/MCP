import json

import pytest

from investigator_shared.registry import get_repository, registry_path


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    return tmp_path


def save_record(repository_id: str, destination, sha: str) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "repositories": {
                    repository_id: {
                        "repository_id": repository_id,
                        "url": "https://github.com/example/service",
                        "owner": "example",
                        "name": "service",
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
    get_repository(repository_id)
