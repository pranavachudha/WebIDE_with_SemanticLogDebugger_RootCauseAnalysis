import os
import json
import uuid
import sys
import re
import subprocess
from pathlib import Path

# Add backend directory to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_db.chroma_store import add_bug_to_db

EXCEPTION_NAMES = [
    "ImportError",
    "ModuleNotFoundError",
    "AttributeError",
    "TypeError",
    "NameError",
    "ValueError",
    "AssertionError",
    "IndexError",
    "KeyError",
    "ZeroDivisionError",
]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _parse_bug_info(text: str) -> dict:
    info = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key.strip()] = value.strip().strip('"')
    return info


def _extract_changed_file(patch: str) -> str:
    match = re.search(r"^\+\+\+ b/(.+)$", patch, re.MULTILINE)
    return match.group(1) if match else ""


def _extract_patch_hunks(patch: str) -> tuple[str, str]:
    removed = []
    added = []
    for line in patch.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return "\n".join(removed[:120]), "\n".join(added[:120])


def _infer_exception(text: str) -> str:
    for name in EXCEPTION_NAMES:
        if name in text:
            return name
    if "pytest.raises" in text or "assert" in text.lower():
        return "AssertionError"
    if "import " in text or "from " in text:
        return "ImportError"
    return "RuntimeError"


def _summarize_root_cause(exception_type: str, patch: str, file_path: str) -> str:
    lowered = patch.lower()
    if exception_type in {"ImportError", "ModuleNotFoundError"}:
        return "Import/dependency behavior changed; fixes commonly adjust module resolution, optional dependencies, or exported names."
    if "none" in lowered:
        return "Patch indicates a missing None guard or null value propagation before an operation."
    if "len(" in lowered or "index" in lowered:
        return "Patch suggests a boundary, collection length, or indexing condition was corrected."
    if "type" in lowered or "isinstance" in lowered:
        return "Patch suggests runtime type handling or argument normalization was corrected."
    if "assert" in lowered:
        return "Failing behavior was exposed by an assertion and fixed by aligning implementation with the tested contract."
    return f"Historical BugsInPy patch in {file_path or 'project code'} changed the faulty implementation path."


def _run_failing_test(bug_dir: Path) -> str:
    script = bug_dir / "run_test.sh"
    if not script.exists():
        return ""
    try:
        completed = subprocess.run(
            ["bash", str(script)],
            cwd=str(bug_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return f"{completed.stdout}\n{completed.stderr}".strip()
    except Exception as exc:
        return f"Test execution skipped/failed: {exc}"


def build_bug_record(project: str, bug_dir: Path, run_tests: bool = False) -> dict:
    bug_info = _parse_bug_info(_read_text(bug_dir / "bug.info"))
    patch = _read_text(bug_dir / "bug_patch.txt")
    failing_output = _run_failing_test(bug_dir) if run_tests else ""
    buggy_code, fixed_code = _extract_patch_hunks(patch)
    file_path = _extract_changed_file(patch)
    exception_type = _infer_exception("\n".join([failing_output, patch, _read_text(bug_dir / "requirements.txt")]))
    bug_id = f"{project}-{bug_dir.name}"
    return {
        "bug_id": bug_id,
        "project": project,
        "exception_type": exception_type,
        "stack_trace": failing_output,
        "buggy_code": buggy_code,
        "fixed_code": fixed_code,
        "patch": patch[:8000],
        "root_cause_summary": _summarize_root_cause(exception_type, patch, file_path),
        "failing_function": "",
        "imports": re.findall(r"^\s*(?:from\s+\S+\s+import\s+.+|import\s+.+)$", buggy_code, re.MULTILINE),
        "file_path": file_path or bug_info.get("test_file", ""),
        "metadata": bug_info,
    }


def ingest_bugsinpy_dataset(dataset_path: str, limit: int | None = 150, run_tests: bool = False) -> dict:
    dataset_root = Path(dataset_path)
    if not dataset_root.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        candidates = [
            Path.cwd() / dataset_path,
            repo_root / dataset_path,
            repo_root / "dataset" / "BugsInPy",
        ]
        dataset_root = next((path.resolve() for path in candidates if path.exists()), candidates[-1].resolve())
    projects_dir = dataset_root / "projects"
    if not projects_dir.exists():
        raise FileNotFoundError(f"BugsInPy projects directory not found: {projects_dir}")

    records = []
    for project_dir in sorted(projects_dir.iterdir()):
        bugs_dir = project_dir / "bugs"
        if not bugs_dir.exists():
            continue
        for bug_dir in sorted([path for path in bugs_dir.iterdir() if path.is_dir()], key=lambda item: item.name):
            record = build_bug_record(project_dir.name, bug_dir, run_tests=run_tests)
            add_bug_to_db(
                bug_id=record["bug_id"],
                exception_type=record["exception_type"],
                traceback_str=record["stack_trace"],
                buggy_code=record["buggy_code"],
                fixed_code=record["fixed_code"],
                rca_summary=record["root_cause_summary"],
                patch=record["patch"],
                project=record["project"],
                failing_function=record["failing_function"],
                imports=record["imports"],
                file_path=record["file_path"],
            )
            records.append(record)
            if limit and len(records) >= limit:
                return {"indexed": len(records), "dataset_path": str(dataset_root), "sample": records[:3]}
    return {"indexed": len(records), "dataset_path": str(dataset_root), "sample": records[:3]}


def ingest_mock_data():
    """
    Since cloning and processing the full BugsInPy dataset takes a long time,
    we'll start by ingesting a few mock samples based on common patterns.
    """
    mock_bugs = [
        {
            "exception_type": "ModuleNotFoundError",
            "traceback_str": "Traceback (most recent call last):\n  File \"test.py\", line 1, in <module>\n    import numpy as np\nModuleNotFoundError: No module named 'numpy'",
            "buggy_code": "import numpy as np\n\ndef calculate():\n    return np.array([1, 2, 3])",
            "fixed_code": "# Run pip install numpy\nimport numpy as np\n\ndef calculate():\n    return np.array([1, 2, 3])",
            "rca_summary": "The environment was missing the 'numpy' package. Fixed by adding numpy to requirements and installing it."
        },
        {
            "exception_type": "AttributeError",
            "traceback_str": "Traceback (most recent call last):\n  File \"test.py\", line 5, in <module>\n    result = process_data(None)\n  File \"test.py\", line 2, in process_data\n    data.append(1)\nAttributeError: 'NoneType' object has no attribute 'append'",
            "buggy_code": "def process_data(data):\n    data.append(1)\n    return data\n\nresult = process_data(None)",
            "fixed_code": "def process_data(data):\n    if data is None:\n        data = []\n    data.append(1)\n    return data\n\nresult = process_data(None)",
            "rca_summary": "A null reference (None) was passed to a function expecting a list. Fixed by adding a null check and initializing an empty list."
        },
        {
            "exception_type": "IndexError",
            "traceback_str": "Traceback (most recent call last):\n  File \"test.py\", line 3, in <module>\n    print(my_list[5])\nIndexError: list index out of range",
            "buggy_code": "my_list = [1, 2, 3]\n\nprint(my_list[5])",
            "fixed_code": "my_list = [1, 2, 3]\n\nif len(my_list) > 5:\n    print(my_list[5])",
            "rca_summary": "Attempted to access an index beyond the bounds of the list. Fixed by adding a bounds check."
        }
    ]
    
    print("Ingesting curated semantic debugger seed bugs...")
    for index, bug in enumerate(mock_bugs, start=1):
        bug_id = f"semantic-seed-{index}-{bug['exception_type']}"
        add_bug_to_db(
            bug_id=bug_id,
            exception_type=bug["exception_type"],
            traceback_str=bug["traceback_str"],
            buggy_code=bug["buggy_code"],
            fixed_code=bug["fixed_code"],
            rca_summary=bug["rca_summary"],
            project="semantic-debugger-seed",
            patch=f"--- buggy\n+++ fixed\n{bug['fixed_code']}",
        )
        print(f"Ingested {bug['exception_type']} bug.")
        
    print("Ingestion complete!")

if __name__ == "__main__":
    default_dataset = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "BugsInPy")
    if os.path.exists(default_dataset):
        print(json.dumps(ingest_bugsinpy_dataset(default_dataset, limit=150), indent=2))
    else:
        ingest_mock_data()
