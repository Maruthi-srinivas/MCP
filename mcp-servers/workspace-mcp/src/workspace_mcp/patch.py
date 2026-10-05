"""Apply a small unified diff in Python. A context mismatch writes nothing."""

from investigator_shared.errors import ToolFailure


def parse_diff(diff: str) -> list[dict]:
    """Return one entry per file: path and hunks. A bad hunk is PATCH_REJECTED."""
    lines = str(diff).splitlines()
    files: list[dict] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise ToolFailure("PATCH_REJECTED", "Diff is missing a file header.", False)
        path = _path_from_header(lines[index + 1][4:])
        index += 2
        hunks = []
        while index < len(lines) and lines[index].startswith("@@"):
            old_start, old_count, new_count = _hunk_counts(lines[index])
            index += 1
            body = []
            while index < len(lines) and not lines[index].startswith(("@@", "--- ")):
                line = lines[index]
                if line.startswith((" ", "+", "-")) or line == r"\ No newline at end of file":
                    if not line.startswith("\\"):
                        body.append(line)
                elif line == "":
                    body.append(" ")
                else:
                    raise ToolFailure("PATCH_REJECTED", "Diff line has no prefix.", False)
                index += 1
            hunks.append({"old_start": old_start, "old_count": old_count, "new_count": new_count, "lines": body})
        if not hunks:
            raise ToolFailure("PATCH_REJECTED", "Diff file has no hunks.", False)
        files.append({"path": path, "hunks": hunks})
    if not files:
        raise ToolFailure("PATCH_REJECTED", "Diff has no files.", False)
    return files


def apply_to_text(original: str, hunks: list[dict]) -> str:
    """Return the new text. Raise PATCH_REJECTED when context does not match."""
    lines = original.splitlines(keepends=True)
    offset = 0
    for hunk in hunks:
        start = hunk["old_start"] - 1 + offset
        if start < 0:
            raise ToolFailure("PATCH_REJECTED", "Hunk starts before the file.", False)
        new_chunk: list[str] = []
        cursor = start
        consumed = 0
        for raw in hunk["lines"]:
            tag, text = raw[0], raw[1:]
            if tag in {" ", "-"}:
                _require_match(lines, cursor, text)
                if tag == " ":
                    new_chunk.append(_with_newline(lines[cursor]))
                cursor += 1
                consumed += 1
            elif tag == "+":
                new_chunk.append(text + "\n")
        context = sum(1 for raw in hunk["lines"] if raw.startswith(" "))
        added = sum(1 for raw in hunk["lines"] if raw.startswith("+"))
        if consumed != hunk["old_count"] or context + added != hunk["new_count"]:
            raise ToolFailure("PATCH_REJECTED", "Hunk counts do not match the body.", False)
        lines[start:cursor] = new_chunk
        offset += len(new_chunk) - (cursor - start)
    return "".join(lines)


def _require_match(lines: list[str], cursor: int, text: str) -> None:
    if cursor >= len(lines) or lines[cursor].rstrip("\r\n") != text:
        raise ToolFailure("PATCH_REJECTED", "Patch context does not match the file.", False)


def _with_newline(line: str) -> str:
    return line if line.endswith("\n") else line + "\n"


def _path_from_header(header: str) -> str:
    path = header.strip().split("\t", 1)[0]
    if path in {"/dev/null", "dev/null"}:
        raise ToolFailure("PATCH_REJECTED", "Creating a new file is not supported.", False)
    if path.startswith("b/") or path.startswith("a/"):
        path = path[2:]
    return path


def _hunk_counts(header: str) -> tuple[int, int, int]:
    try:
        body = header.split("@@")[1].strip().split()
        old_part = body[0][1:]
        new_part = body[1][1:]
    except (IndexError, ValueError) as exc:
        raise ToolFailure("PATCH_REJECTED", "Hunk header is invalid.", False) from exc
    old_start, old_count = _count(old_part)
    _, new_count = _count(new_part)
    return old_start, old_count, new_count


def _count(part: str) -> tuple[int, int]:
    if "," in part:
        start, count = part.split(",", 1)
        return int(start), int(count)
    return int(part), 1
