"""Functions, classes, and imports from one parsed file."""

import ast


def collect(tree: ast.AST, path: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Return functions (including methods), classes, and imports for one file."""
    functions: list[dict] = []
    classes: list[dict] = []
    imports: list[dict] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._class_depth = 0
            self._function_depth = 0

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            classes.append({"name": node.name, "path": path, "line": node.lineno})
            self._class_depth += 1
            self.generic_visit(node)
            self._class_depth -= 1

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            functions.append(_function(node, path, self._class_depth, self._function_depth, async_def=False))
            self._function_depth += 1
            self.generic_visit(node)
            self._function_depth -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            functions.append(_function(node, path, self._class_depth, self._function_depth, async_def=True))
            self._function_depth += 1
            self.generic_visit(node)
            self._function_depth -= 1

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                imports.append(
                    {"path": path, "line": node.lineno, "module": alias.name, "names": [alias.name], "level": 0}
                )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            names = [alias.name for alias in node.names if alias.name != "*"]
            if not names and node.module is None:
                return
            imports.append(
                {
                    "path": path,
                    "line": node.lineno,
                    "module": node.module or "",
                    "names": names,
                    "level": node.level or 0,
                }
            )

    Visitor().visit(tree)
    return functions, classes, imports


def _function(node: ast.AST, path: str, class_depth: int, function_depth: int, async_def: bool) -> dict:
    if class_depth and function_depth == 0:
        kind = "method"
    elif async_def:
        kind = "async_function"
    else:
        kind = "function"
    return {"name": node.name, "kind": kind, "path": path, "line": node.lineno}
