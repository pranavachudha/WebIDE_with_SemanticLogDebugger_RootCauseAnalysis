import re
from typing import Any

from parser.traceback_parser import parse_traceback


PY_TRACEBACK_START = "Traceback (most recent call last):"
EXCEPTION_LINE = re.compile(
    r"^\s*(?P<type>[A-Za-z_][\w.]*?(?:Error|Exception|Failure|Fault))"
    r"(?::\s*(?P<message>.*))?\s*$"
)
INLINE_EXCEPTION = re.compile(
    r"(?P<type>[A-Za-z_][\w.]*?(?:Error|Exception|Failure|Fault))"
    r"(?::\s*(?P<message>[^\r\n]*))?"
)
SEVERITY_MARKER = re.compile(r"\b(ERROR|CRITICAL|FATAL|SEVERE|EXCEPTION|TRACEBACK)\b", re.IGNORECASE)


def _numbered_excerpt(lines: list[str], start: int, end: int, radius: int = 8) -> str:
    excerpt_start = max(0, start - radius)
    excerpt_end = min(len(lines), end + radius + 1)
    return "\n".join(
        f"{idx + 1}: {line}" for idx, line in enumerate(lines[excerpt_start:excerpt_end], excerpt_start)
    )


def _traceback_blocks(lines: list[str]) -> list[dict[str, Any]]:
    blocks = []
    for index, line in enumerate(lines):
        marker_index = line.find(PY_TRACEBACK_START)
        if marker_index == -1:
            continue

        block_lines = [line[marker_index:]]
        end_index = index
        for cursor in range(index + 1, len(lines)):
            block_lines.append(lines[cursor])
            end_index = cursor
            if EXCEPTION_LINE.match(lines[cursor]):
                break

        blocks.append(
            {
                "start": index,
                "end": end_index,
                "text": "\n".join(block_lines),
            }
        )
    return blocks


def parse_log_failure(log_text: str, filename: str = "uploaded.log") -> dict[str, Any]:
    """Extract the most useful failure signal from an uploaded log file."""
    normalized = (log_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()

    if not normalized.strip():
        return {
            "type": "EmptyLogError",
            "message": "The uploaded log file is empty.",
            "traceback": "",
            "line_number": -1,
            "file_name": filename,
            "failing_function": "log",
            "call_stack": [],
            "code_context": {
                "imports": [],
                "surrounding_code": "",
                "failing_function": "log",
                "class_context": "",
                "ast_summary": ["LogFile"],
            },
            "source_type": "log",
            "log_line_number": -1,
            "candidate_count": 0,
        }

    blocks = _traceback_blocks(lines)
    if blocks:
        block = blocks[-1]
        parsed = parse_traceback(block["text"])
        excerpt = _numbered_excerpt(lines, block["start"], block["end"])
        return {
            "type": parsed.get("exception_type", "UnknownError"),
            "message": parsed.get("message", ""),
            "traceback": block["text"],
            "line_number": parsed.get("line_number", -1),
            "file_name": filename,
            "failing_function": parsed.get("failing_function", "") or "log",
            "call_stack": parsed.get("call_stack", []),
            "code_context": {
                "imports": [],
                "surrounding_code": excerpt,
                "failing_function": parsed.get("failing_function", "") or "log",
                "class_context": "",
                "ast_summary": ["LogTraceback", f"Candidates:{len(blocks)}"],
            },
            "source_type": "log",
            "log_line_number": block["start"] + 1,
            "candidate_count": len(blocks),
        }

    candidates = []
    for index, line in enumerate(lines):
        exception_match = INLINE_EXCEPTION.search(line)
        has_severity = SEVERITY_MARKER.search(line)
        if exception_match or has_severity:
            candidates.append(
                {
                    "index": index,
                    "line": line,
                    "exception": exception_match,
                    "has_severity": bool(has_severity),
                }
            )

    if not candidates:
        candidates.append({"index": len(lines) - 1, "line": lines[-1], "exception": None, "has_severity": False})

    candidate = sorted(candidates, key=lambda item: (item["has_severity"], item["index"]))[-1]
    exception_match = candidate["exception"]
    exception_type = exception_match.group("type") if exception_match else "LogError"
    message = (exception_match.group("message") or "").strip() if exception_match else candidate["line"].strip()
    excerpt = _numbered_excerpt(lines, candidate["index"], candidate["index"], radius=10)

    return {
        "type": exception_type,
        "message": message or candidate["line"].strip(),
        "traceback": excerpt,
        "line_number": candidate["index"] + 1,
        "file_name": filename,
        "failing_function": "log",
        "call_stack": [
            {
                "file": filename,
                "line_number": candidate["index"] + 1,
                "function": "log",
            }
        ],
        "code_context": {
            "imports": [],
            "surrounding_code": excerpt,
            "failing_function": "log",
            "class_context": "",
            "ast_summary": ["LogLine", f"Candidates:{len(candidates)}"],
        },
        "source_type": "log",
        "log_line_number": candidate["index"] + 1,
        "candidate_count": len(candidates),
    }
