import pytest

from investigator_shared.registry import get_repository


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    return tmp_path


def save_record(repository_id: str, destination, sha: str) -> None:
    from investigator_shared.registry import registry_path
    import json

    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "repositories": {
                    repository_id: {
                        "repository_id": repository_id,
                        "url": "https://github.com/example/history",
                        "owner": "example",
                        "name": "history",
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
