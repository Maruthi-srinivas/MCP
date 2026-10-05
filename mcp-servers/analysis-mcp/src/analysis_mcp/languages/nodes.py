"""Small helpers shared by the language modules."""


def text(node) -> str:
    """Decoded source for one tree-sitter node."""
    raw = node.text or b""
    return raw.decode("utf-8", errors="replace")


def line(node) -> int:
    """1-based line. Tree-sitter rows start at 0."""
    return node.start_point[0] + 1


def ident(node) -> str:
    """Name text, or an empty string when the field is missing."""
    if node is None:
        return ""
    return text(node)


def string_value(node) -> str:
    """Strip quotes from a string literal."""
    raw = text(node).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"', "`"}:
        return raw[1:-1]
    return raw


def walk(node):
    """Yield a node and then its children."""
    yield node
    for child in node.children:
        yield from walk(child)
