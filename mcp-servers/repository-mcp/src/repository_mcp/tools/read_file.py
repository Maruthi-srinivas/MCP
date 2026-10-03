"""Read a bounded line range from one file inside the workspace."""

from repository_mcp.config import get_settings
from repository_mcp.errors import ToolFailure
from repository_mcp.logging import observed_tool
from repository_mcp.workspace.paths import repository_root, resolve_inside


@observed_tool
def read_file(
    repository_id: str,
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> dict:
    """Return a line window from a text file. Large files and long windows are bounded."""
    if start_line < 1 or (end_line is not None and end_line < start_line):
        raise ToolFailure("INVALID_PATH", "Line range must start at 1 or later and end after the start.", False)

    settings = get_settings()
    root = repository_root(repository_id)
    file_path = resolve_inside(root, path)
    if file_path.is_dir():
        raise ToolFailure("INVALID_PATH", "Path is a directory.", False)
    if not file_path.is_file():
        raise ToolFailure("FILE_NOT_FOUND", f"{path} was not found.", False)

    size = file_path.stat().st_size
    if size > settings.max_file_bytes:
        raise ToolFailure("FILE_TOO_LARGE", "File exceeds the configured size limit.", False)

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolFailure("FILE_TOO_LARGE", "File is not UTF-8 text.", False) from exc

    lines = text.splitlines()
    total_lines = len(lines)
    requested_end = total_lines if end_line is None else end_line
    window_end = min(requested_end, start_line + settings.max_read_lines - 1, total_lines)
    if start_line > total_lines:
        selected: list[str] = []
        actual_end = start_line - 1
    else:
        selected = lines[start_line - 1 : window_end]
        actual_end = start_line + len(selected) - 1 if selected else start_line - 1

    visible_end = min(requested_end, total_lines)
    truncated = bool(selected) and actual_end < visible_end

    return {
        "repository_id": repository_id,
        "path": file_path.resolve().relative_to(root.resolve()).as_posix(),
        "start_line": start_line,
        "end_line": actual_end,
        "content": "\n".join(selected),
        "truncated": truncated,
        "total_lines": total_lines,
    }
