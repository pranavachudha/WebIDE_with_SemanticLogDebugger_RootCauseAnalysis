import re
import csv
import io
import base64
from typing import Any

from parser.traceback_parser import parse_traceback


def csv_to_text(csv_content: str) -> str:
    # Parse the CSV content
    f = io.StringIO(csv_content)
    try:
        reader = csv.reader(f)
        rows = list(reader)
    except Exception as e:
        # Fallback to returning the raw text if parsing fails
        return f"Error parsing CSV content: {e}\n{csv_content}"

    if not rows:
        return ""

    # Check if there are headers
    headers = [h.strip().lower() for h in rows[0]]
    
    # Check if this looks like a header row or just data
    has_header = any(h in ['level', 'severity', 'message', 'traceback', 'exception', 'timestamp', 'log', 'time', 'text'] for h in headers)
    
    output = []
    start_row = 1 if has_header else 0
    header_names = rows[0] if has_header else [f"Col{i+1}" for i in range(len(rows[0]))]

    for row_idx, row in enumerate(rows[start_row:], start=start_row+1):
        if len(row) == 1:
            val_str = str(row[0]).strip()
            output.append(val_str)
        else:
            row_parts = []
            tracebacks = []
            for col_idx, val in enumerate(row):
                if col_idx >= len(header_names):
                    continue
                col_name = header_names[col_idx].strip()
                val_str = str(val).strip()
                if not val_str:
                    continue
                
                # If the column value contains a traceback, save it to append at the end
                if "Traceback (most recent call last):" in val_str or "traceback" in col_name.lower():
                    tracebacks.append(val_str)
                else:
                    row_parts.append(f"{col_name}: {val_str}")
            
            row_text = f"Row {row_idx}: " + " | ".join(row_parts)
            output.append(row_text)
            for tb in tracebacks:
                output.append(tb)
            
    return "\n".join(output)


def excel_to_text(base64_content: str) -> str:
    try:
        file_bytes = base64.b64decode(base64_content)
    except Exception as e:
        return f"Error decoding base64 Excel content: {e}"
        
    try:
        import pandas as pd
        # Load the Excel file
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets = excel_file.sheet_names
    except Exception as e:
        return f"Error loading Excel workbook: {e}"

    output = []
    for sheet_name in sheets:
        try:
            df = excel_file.parse(sheet_name)
            output.append(f"--- Sheet: {sheet_name} ---")
            if df.empty:
                output.append("(Empty Sheet)")
                continue
            
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            sheet_csv_content = csv_buffer.getvalue()
            output.append(csv_to_text(sheet_csv_content))
        except Exception as e:
            output.append(f"Error parsing sheet {sheet_name}: {e}")
            
    return "\n".join(output)


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


def _parse_csv_content(csv_content: str) -> list[list[str]]:
    f = io.StringIO(csv_content)
    try:
        reader = csv.reader(f)
        return list(reader)
    except Exception:
        return []


def _parse_excel_content(base64_content: str) -> list[list[str]]:
    try:
        file_bytes = base64.b64decode(base64_content)
    except Exception:
        return []
    try:
        import pandas as pd
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        all_rows = []
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            if df.empty:
                continue
            headers = [str(c) for c in df.columns]
            all_rows.append(headers)
            for row in df.values:
                all_rows.append([str(val) if pd.notna(val) else "" for val in row])
        return all_rows
    except Exception:
        return []


EXCEPTION_PATTERN = re.compile(
    r"\b([A-Za-z0-9_.]*(?:Error|Exception|Failure|Fault))\b",
    re.IGNORECASE
)


def _extract_exception_type(text: str) -> str | None:
    if not text:
        return None
    matches = EXCEPTION_PATTERN.findall(text)
    if not matches:
        return None
    
    generic_names = {"error", "exception", "failure", "fault"}
    specific_matches = [m for m in matches if m.lower() not in generic_names]
    
    if specific_matches:
        # Return the last specific match (e.g. java.io.IOException)
        return specific_matches[-1]
    
    # Capitalize the generic ones for cleaner diagnostic values
    generic_match = matches[0].lower()
    if generic_match == "exception":
        return "Exception"
    elif generic_match == "error":
        return "Error"
    elif generic_match == "failure":
        return "Failure"
    elif generic_match == "fault":
        return "Fault"
    return matches[0]


def _format_sheet_row(row_cells: list[str], row_idx: int, header_names: list[str]) -> str:
    row_parts = []
    for col_idx, val in enumerate(row_cells):
        if col_idx < len(header_names):
            col_name = header_names[col_idx].strip()
        else:
            col_name = f"Col{col_idx+1}"
        val_str = str(val).strip()
        if val_str:
            row_parts.append(f"{col_name}: {val_str}")
    return f"Row {row_idx}: " + " | ".join(row_parts)


def parse_structured_log(rows: list[list[str]], filename: str, parsed_log_text: str) -> dict[str, Any] | None:
    if not rows or len(rows) < 2:
        return None

    headers = [h.strip().lower() for h in rows[0]]
    
    level_idx = -1
    message_idx = -1
    traceback_idx = -1
    line_idx = -1
    has_datetime = False
    
    level_priority = 0
    message_priority = 0
    traceback_priority = 0
    line_priority = 0
    details_idx = -1

    for idx, h in enumerate(headers):
        h_norm = h.strip().lower()
        
        # Level mapping
        if h_norm in ['level', 'severity', 'loglevel', 'log_level']:
            p = 2
            if p > level_priority:
                level_priority = p
                level_idx = idx
        elif h_norm in ['status']:
            p = 1
            if p > level_priority:
                level_priority = p
                level_idx = idx
                
        # Message mapping
        if h_norm in ['message', 'content', 'msg', 'text', 'log']:
            p = 3
            if p > message_priority:
                message_priority = p
                message_idx = idx
        elif h_norm in ['info', 'description']:
            p = 2
            if p > message_priority:
                message_priority = p
                message_idx = idx
        elif h_norm in ['detail', 'details']:
            p = 1
            if p > message_priority:
                message_priority = p
                message_idx = idx

        # Traceback mapping
        if h_norm in ['traceback', 'stacktrace', 'stack_trace', 'stack']:
            p = 2
            if p > traceback_priority:
                traceback_priority = p
                traceback_idx = idx
        elif h_norm in ['exception', 'error']:
            p = 1
            if p > traceback_priority:
                traceback_priority = p
                traceback_idx = idx

        # Line mapping
        if h_norm in ['lineid', 'linenumber', 'line_id', 'line_number', 'line']:
            p = 2
            if p > line_priority:
                line_priority = p
                line_idx = idx
        elif h_norm in ['row', 'rowid']:
            p = 1
            if p > line_priority:
                line_priority = p
                line_idx = idx

        # Track details/detail separately for traceback fallback
        if h_norm in ['detail', 'details']:
            details_idx = idx

        # Check date/time/timestamp
        if h_norm in ['date', 'time', 'timestamp', 'datetime', 'created_at']:
            has_datetime = True

    # Fallback details column to traceback if traceback is not explicitly defined
    if traceback_idx == -1 and details_idx != -1 and details_idx != message_idx:
        traceback_idx = details_idx

    # Check if this sheet is structured log
    if message_idx == -1 and traceback_idx == -1:
        return None

    has_other_meta = (level_idx != -1) or (line_idx != -1) or (traceback_idx != -1) or has_datetime
    if not has_other_meta:
        return None

    failing_row_idx = -1
    max_priority = 0
    candidate_count = 0

    for row_idx in range(1, len(rows)):
        row = rows[row_idx]
        if not row:
            continue
            
        lvl = row[level_idx].strip().upper() if (level_idx != -1 and level_idx < len(row)) else ""
        msg = row[message_idx].strip() if (message_idx != -1 and message_idx < len(row)) else ""
        tb = row[traceback_idx].strip() if (traceback_idx != -1 and traceback_idx < len(row)) else ""

        priority = 0
        
        # Check traceback/exception
        if tb and any(indicator in tb.lower() for indicator in ["traceback", "exception", "error", "at "]):
            priority = 3
        # Check level
        elif lvl in ["ERROR", "FATAL", "CRITICAL", "SEVERE", "FAIL", "FAILURE"]:
            priority = 3
        elif lvl in ["WARN", "WARNING"]:
            priority = 2
        
        # Check if msg contains exception/error
        if priority < 3:
            if "exception" in msg.lower() or "error" in msg.lower():
                priority = max(priority, 3 if "exception" in msg.lower() else 2)

        if priority > 0:
            candidate_count += 1
            if priority >= max_priority:
                max_priority = priority
                failing_row_idx = row_idx

    if failing_row_idx == -1:
        return {
            "type": "NoFailureDetected",
            "message": "No exception traceback or error severity markers were detected in the log file.",
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
            "parsed_log_text": parsed_log_text,
            "no_error_detected": True,
        }

    failing_row = rows[failing_row_idx]
    
    line_number = failing_row_idx + 1
    if line_idx != -1 and line_idx < len(failing_row):
        try:
            line_number = int(failing_row[line_idx].strip())
        except ValueError:
            pass

    msg = failing_row[message_idx].strip() if (message_idx != -1 and message_idx < len(failing_row)) else ""
    tb = failing_row[traceback_idx].strip() if (traceback_idx != -1 and traceback_idx < len(failing_row)) else ""

    # Surrounding context
    excerpt_lines = []
    for r_idx in range(max(1, failing_row_idx - 8), min(len(rows), failing_row_idx + 9)):
        r_cells = rows[r_idx]
        excerpt_lines.append(_format_sheet_row(r_cells, r_idx + 1, rows[0]))
    excerpt = "\n".join(excerpt_lines)

    traceback_val = tb if tb else excerpt
    
    exception_type = _extract_exception_type(tb)
    if not exception_type:
        exception_type = _extract_exception_type(msg)
    if not exception_type:
        exception_type = "LogError"

    return {
        "type": exception_type,
        "message": f"{msg}: {tb}" if (msg and tb and msg != tb) else (tb if tb else msg),
        "traceback": traceback_val,
        "line_number": line_number,
        "file_name": filename,
        "failing_function": "log",
        "call_stack": [
            {
                "file": filename,
                "line_number": line_number,
                "function": "log",
            }
        ],
        "code_context": {
            "imports": [],
            "surrounding_code": excerpt,
            "failing_function": "log",
            "class_context": "",
            "ast_summary": ["LogLine", f"Candidates:{candidate_count}"],
        },
        "source_type": "log",
        "log_line_number": line_number,
        "candidate_count": candidate_count,
        "parsed_log_text": parsed_log_text,
    }


def parse_log_failure(log_text: str, filename: str = "uploaded.log") -> dict[str, Any]:
    """Extract the most useful failure signal from an uploaded log file."""
    filename_lower = filename.lower()
    rows = []
    parsed_log_text = log_text

    if filename_lower.endswith(".xlsx") or filename_lower.endswith(".xls"):
        parsed_log_text = excel_to_text(log_text)
        rows = _parse_excel_content(log_text)
    elif filename_lower.endswith(".csv"):
        parsed_log_text = csv_to_text(log_text)
        rows = _parse_csv_content(log_text)

    if rows:
        structured_result = parse_structured_log(rows, filename, parsed_log_text)
        if structured_result is not None:
            return structured_result

    log_text = parsed_log_text

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
            "parsed_log_text": log_text,
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
            "parsed_log_text": log_text,
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
        return {
            "type": "NoFailureDetected",
            "message": "No exception traceback or error severity markers were detected in the log file.",
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
            "parsed_log_text": log_text,
            "no_error_detected": True,
        }

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
        "parsed_log_text": log_text,
    }
