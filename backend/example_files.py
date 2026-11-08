"""Read and delete disk-backed examples without exposing other project files."""

import hmac
import os
from pathlib import Path

from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, SecretStr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"
ENV_PATH = Path(__file__).with_name(".env")
PREDEFINED_EXAMPLES = frozenset({
    "attribute_error.py", "complex_call_stack_error.py", "division_error.py",
    "examples.py", "index.error.py", "key_error.py", "main.py", "name_error.py",
    "oop_complex_error.py", "type_error.py",
})
router = APIRouter(prefix="/workspace/examples", tags=["Workspace"])


class DeleteExamplesRequest(BaseModel):
    filenames: list[str] = Field(default_factory=list, max_length=500)
    password: SecretStr | None = None
    delete_folder: bool = False


def _directory() -> Path:
    root = EXAMPLES_DIR.resolve()
    if EXAMPLES_DIR.is_symlink() or root != PROJECT_ROOT.resolve() / "examples":
        raise HTTPException(400, "The examples directory must be inside this project.")
    if root.exists() and not root.is_dir():
        raise HTTPException(400, "The examples path is not a directory.")
    return root


def _file(root: Path, name: str) -> Path:
    if not name or "/" in name or "\\" in name or ":" in name or "\x00" in name or not name.endswith(".py"):
        raise HTTPException(400, "Invalid example filename.")
    path = root / name
    if path.is_symlink() or path.resolve().parent != root:
        raise HTTPException(400, "Example files must stay inside the examples directory.")
    if path.exists() and not path.is_file():
        raise HTTPException(400, "The selected example is not a regular file.")
    return path


@router.get("")
def list_examples(response: Response):
    root = _directory()
    response.headers["Cache-Control"] = "no-store"
    if not root.exists():
        return {"folder_exists": False, "files": []}
    files = []
    for entry in sorted(root.glob("*.py")):
        path = _file(root, entry.name)
        files.append({
            "id": f"example:{entry.name}", "name": entry.name, "type": "file",
            "content": path.read_text(encoding="utf-8"),
            "examplePath": entry.name,
            "isPredefined": entry.name in PREDEFINED_EXAMPLES,
        })
    return {"folder_exists": True, "files": files}


@router.post("/delete")
def delete_examples(request: DeleteExamplesRequest):
    root = _directory()
    names = set(request.filenames)
    if request.delete_folder and root.exists():
        entries = list(root.iterdir())
        if any(entry.is_symlink() or not entry.is_file() or entry.suffix != ".py" for entry in entries):
            raise HTTPException(400, "This folder contains other disk files. Delete individual examples instead.")
        names.update(entry.name for entry in entries)

    # Validate every target and authenticate the entire operation before deleting.
    paths = [_file(root, name) for name in sorted(names)]
    if names & PREDEFINED_EXAMPLES:
        expected = os.getenv("EXAMPLE_DELETE_PASSWORD") or dotenv_values(ENV_PATH).get("EXAMPLE_DELETE_PASSWORD")
        if not expected:
            raise HTTPException(503, "Set EXAMPLE_DELETE_PASSWORD in backend/.env before deleting predefined examples.")
        supplied = request.password.get_secret_value() if request.password else ""
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(403, "Incorrect password for predefined example files.")

    try:
        for path in paths:
            path.unlink(missing_ok=True)
        if request.delete_folder and root.exists():
            root.rmdir()
    except OSError as exc:
        raise HTTPException(409, "Could not delete all selected disk files. Refresh the examples and try again.") from exc
    return {"deleted": sorted(names), "folder_deleted": request.delete_folder}
