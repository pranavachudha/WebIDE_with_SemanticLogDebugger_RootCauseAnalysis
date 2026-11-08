"""Exercise permanent deletion against temporary copies, never the real examples."""

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
example_files = importlib.import_module("example_files")


class ExampleFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix=".test-examples-", dir=BACKEND)
        self.root = Path(self.temporary.name).resolve()
        self.assertEqual(self.root.parent, BACKEND)
        self.addCleanup(self.temporary.cleanup)
        self.examples = self.root / "examples"
        self.examples.mkdir()
        for name in example_files.PREDEFINED_EXAMPLES:
            (self.examples / name).write_text("print('fixture')\n", encoding="utf-8")
        self.patches = [
            patch.object(example_files, "PROJECT_ROOT", self.root),
            patch.object(example_files, "EXAMPLES_DIR", self.examples),
            patch.object(example_files, "ENV_PATH", self.root / ".env"),
            patch.dict(os.environ, {"EXAMPLE_DELETE_PASSWORD": "fixture-password"}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        app = FastAPI()
        app.include_router(example_files.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def delete(self, **payload):
        return self.client.post("/workspace/examples/delete", json=payload)

    def test_lists_the_ten_real_files_without_returning_credentials(self):
        response = self.client.get("/workspace/examples")
        self.assertEqual(response.status_code, 200)
        files = response.json()["files"]
        self.assertEqual({file["name"] for file in files}, example_files.PREDEFINED_EXAMPLES)
        self.assertTrue(all(file["isPredefined"] for file in files))
        self.assertNotIn("fixture-password", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_wrong_or_missing_password_preserves_the_disk_file(self):
        for password in [None, "wrong"]:
            response = self.delete(filenames=["key_error.py"], password=password)
            self.assertEqual(response.status_code, 403)
            self.assertTrue((self.examples / "key_error.py").is_file())

    def test_correct_password_removes_the_file_and_it_does_not_reappear(self):
        response = self.delete(filenames=["key_error.py"], password="fixture-password")
        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.examples / "key_error.py").exists())
        for _ in range(2):
            names = {file["name"] for file in self.client.get("/workspace/examples").json()["files"]}
            self.assertNotIn("key_error.py", names)

    def test_other_disk_examples_need_no_password(self):
        path = self.examples / "my_script.py"
        path.write_text("print('mine')", encoding="utf-8")
        response = self.delete(filenames=[path.name])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(path.exists())
        self.assertTrue((self.examples / "key_error.py").exists())

    def test_folder_deletion_authenticates_all_children_before_removal(self):
        response = self.delete(delete_folder=True, password="wrong")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(list(self.examples.iterdir())), 10)
        response = self.delete(delete_folder=True, password="fixture-password")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.examples.exists())
        self.assertEqual(self.client.get("/workspace/examples").json(), {"folder_exists": False, "files": []})

    def test_path_escape_and_invalid_batch_do_not_delete_any_files(self):
        outside = self.root / "outside.py"
        outside.write_text("important", encoding="utf-8")
        for name in ["../outside.py", "..\\outside.py", str(outside), "C:/outside.py", ".env"]:
            response = self.delete(filenames=["key_error.py", name], password="fixture-password")
            self.assertEqual(response.status_code, 400)
            self.assertTrue((self.examples / "key_error.py").is_file())
            self.assertEqual(outside.read_text(encoding="utf-8"), "important")

    def test_unknown_subfolders_are_preserved(self):
        (self.examples / "important").mkdir()
        response = self.delete(delete_folder=True, password="fixture-password")
        self.assertEqual(response.status_code, 400)
        self.assertTrue((self.examples / "key_error.py").exists())

    def test_local_dotenv_and_environment_precedence(self):
        (self.root / ".env").write_text("EXAMPLE_DELETE_PASSWORD=local-password\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            response = self.delete(filenames=["key_error.py"], password="local-password")
        self.assertEqual(response.status_code, 200)
        response = self.delete(filenames=["main.py"], password="local-password")
        self.assertEqual(response.status_code, 403)
        self.assertTrue((self.examples / "main.py").exists())

    def test_missing_configuration_fails_without_deleting(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.delete(filenames=["key_error.py"], password="fixture-password")
        self.assertEqual(response.status_code, 503)
        self.assertTrue((self.examples / "key_error.py").exists())

    def test_rejects_a_directory_outside_this_project(self):
        with patch.object(example_files, "EXAMPLES_DIR", self.root):
            response = self.delete(filenames=["key_error.py"], password="fixture-password")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(list(self.examples.glob("*.py"))), 10)


if __name__ == "__main__":
    unittest.main()
