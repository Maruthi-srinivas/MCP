from repository_mcp.workspace.ids import make_repository_id
from repository_mcp.workspace.registry import get_repository, save_repository


def test_registry_round_trip(workspace):
    repository_id = make_repository_id("https://github.com/example/tiny", "HEAD")
    save_repository(
        {
            "repository_id": repository_id,
            "url": "https://github.com/example/tiny",
            "owner": "example",
            "name": "tiny",
            "ref": "main",
            "resolved_commit": "abc123",
            "workspace_path": str(workspace / repository_id),
            "status": "ready",
        }
    )
    record = get_repository(repository_id)
    assert record["resolved_commit"] == "abc123"
    assert record["ref"] == "main"
