import ast
import re
from typing import Any


FRAME_PATTERN = re.compile(r'File "(?P<file>.*?)", line (?P<line>\d+), in (?P<function>.+)')
EXCEPTION_PATTERN = re.compile(r"^(?P<type>[A-Za-z_][\w.]*)(?::\s*(?P<message>.*))?$")


def parse_traceback(traceback_str: str) -> dict[str, Any]:
    """Parse a Python traceback into searchable debugger metadata."""
    result: dict[str, Any] = {
        "exception_type": "UnknownError",
        "message": "",
        "line_number": -1,
        "file": "",
        "failing_function": "",
        "call_stack": [],
    }

    if not traceback_str:
        return result

    lines = [line.rstrip() for line in traceback_str.strip().splitlines() if line.strip()]
    for line in lines:
        match = FRAME_PATTERN.search(line)
        if match:
            frame = {
                "file": match.group("file"),
                "line_number": int(match.group("line")),
                "function": match.group("function").strip(),
            }
            result["call_stack"].append(frame)

    if result["call_stack"]:
        last_frame = result["call_stack"][-1]
        result["file"] = last_frame["file"]
        result["line_number"] = last_frame["line_number"]
        result["failing_function"] = last_frame["function"]

    exception_line = lines[-1] if lines else ""
    exception_match = EXCEPTION_PATTERN.match(exception_line)
    if exception_match:
        result["exception_type"] = exception_match.group("type")
        result["message"] = exception_match.group("message") or ""
    else:
        result["message"] = exception_line

    return result


def extract_code_context(code: str, line_number: int, radius: int = 10) -> dict[str, Any]:
    """Extract imports, enclosing AST node, nearby source, and a compact AST summary."""
    lines = code.splitlines()
    start = max(1, line_number - radius) if line_number > 0 else 1
    end = min(len(lines), line_number + radius) if line_number > 0 else min(len(lines), radius * 2)
    surrounding = "\n".join(
        f"{idx + 1}: {line}" for idx, line in enumerate(lines[start - 1 : end], start - 1)
    )

    context: dict[str, Any] = {
        "imports": [],
        "surrounding_code": surrounding,
        "failing_function": "",
        "class_context": "",
        "ast_summary": [],
    }

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return context

    enclosing_nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            context["imports"].append(ast.unparse(node))
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            node_start = getattr(node, "lineno", 0)
            node_end = getattr(node, "end_lineno", node_start)
            if line_number and node_start <= line_number <= node_end:
                enclosing_nodes.append(node)

    for node in sorted(enclosing_nodes, key=lambda item: getattr(item, "lineno", 0), reverse=True):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not context["failing_function"]:
            context["failing_function"] = node.name
        if isinstance(node, ast.ClassDef) and not context["class_context"]:
            context["class_context"] = node.name

    top_level = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level.append(f"{type(node).__name__}:{node.name}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            top_level.append(type(node).__name__)
        elif isinstance(node, ast.Assign):
            top_level.append("Assign")
        elif isinstance(node, ast.Expr):
            top_level.append("Expr")
    context["ast_summary"] = top_level[:30]
    return context


def build_embedding_document(error: dict[str, Any], code_context: dict[str, Any], code: str = "") -> str:
    """Create the canonical semantic document used for retrieval."""
    return "\n".join(
        [
            f"exception_type: {error.get('type') or error.get('exception_type', '')}",
            f"message: {error.get('message', '')}",
            f"failing_function: {error.get('failing_function') or code_context.get('failing_function', '')}",
            f"imports: {', '.join(code_context.get('imports', []))}",
            f"stack_trace:\n{error.get('traceback', '')}",
            f"code_context:\n{code_context.get('surrounding_code', '')}",
            f"ast_summary: {' | '.join(code_context.get('ast_summary', []))}",
            code[:4000],
        ]
    )
