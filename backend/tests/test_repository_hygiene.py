"""Check fresh-clone seed recovery and local credential configuration."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# These tests exercise the JSON fallback without creating a real Chroma index.
with patch.dict(sys.modules, {"chromadb": None}):
    ingestion = importlib.import_module("ingestion.bugsinpy")
    vector_store = importlib.import_module("vector_db.chroma_store")

from embeddings.generator import _hash_embedding
import sarvam_translate


class BundledBugTests(unittest.TestCase):
    def test_fresh_index_recovers_all_records_and_remains_idempotent(self):
        records = json.loads((BACKEND / "ingestion" / "seed_bugs.json").read_text(encoding="utf-8"))
        expected_ids = {
            "ansible-1", "ansible-10", "ansible-11", "ansible-12", "ansible-13",
            "semantic-seed-1-ModuleNotFoundError", "semantic-seed-2-AttributeError",
            "semantic-seed-3-IndexError",
        }
        self.assertEqual({record["bug_id"] for record in records}, expected_ids)
        self.assertEqual(len(records), len(expected_ids))

        with tempfile.TemporaryDirectory(prefix=".test-index-", dir=BACKEND) as directory:
            self.assertEqual(Path(directory).resolve().parent, BACKEND)
            index_path = Path(directory) / "chroma_data.json"
            with patch.object(vector_store, "JSON_DB_PATH", str(index_path)):
                store = vector_store.SimpleVectorStore()
                self.assertEqual(store.ids, [])
                with (
                    patch.object(vector_store, "traceback_collection", store),
                    patch.object(vector_store, "generate_embedding", side_effect=_hash_embedding),
                    patch.object(ingestion, "add_bug_to_db", vector_store.add_bug_to_db),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    ingestion.ingest_mock_data()
                    ingestion.ingest_mock_data()

                restored = vector_store.SimpleVectorStore()
                self.assertEqual(set(restored.ids), expected_ids)
                self.assertEqual(len(restored.ids), len(expected_ids))
                self.assertEqual(restored.metadatas, records)
                self.assertEqual(len(restored.embeddings), len(records))
                self.assertTrue(all(len(embedding) == 384 for embedding in restored.embeddings))
                matches = restored.query([restored.embeddings[0]], n_results=1)
                self.assertEqual(matches["ids"][0], [restored.ids[0]])


class SarvamCredentialTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client_context = patch.object(sarvam_translate.httpx, "Client")
        self.client_factory = self.client_context.start()
        self.addCleanup(self.client_context.stop)
        self.client = self.client_factory.return_value.__enter__.return_value
        self.client.post.return_value = Mock(
            status_code=200,
            json=lambda: {"translated_text": "translated fixture", "request_id": "test"},
        )

    def test_local_env_is_found_independently_of_working_directory(self):
        with patch.object(sarvam_translate, "dotenv_values", return_value={"SARVAM_API_KEY": " local-fixture-key "}) as config:
            result = sarvam_translate.translate_text("Test text", "hi-IN")
        config.assert_called_once_with(BACKEND / ".env")
        self.assertEqual(self.client.post.call_args.kwargs["headers"]["api-subscription-key"], "local-fixture-key")
        self.assertEqual(result["translated_text"], "translated fixture")

    def test_environment_key_overrides_local_configuration(self):
        os.environ["SARVAM_API_KEY"] = "environment-fixture-key"
        with patch.object(sarvam_translate, "dotenv_values") as config:
            sarvam_translate.translate_text("Test text", "hi-IN")
        config.assert_not_called()
        self.assertEqual(self.client.post.call_args.kwargs["headers"]["api-subscription-key"], "environment-fixture-key")

    def test_missing_key_gives_actionable_error_without_a_request(self):
        with patch.object(sarvam_translate, "dotenv_values", return_value={}):
            with self.assertRaisesRegex(ValueError, r"backend/\.env"):
                sarvam_translate.translate_text("Test text", "hi-IN")
        self.client_factory.assert_not_called()

    def test_unset_local_key_is_not_sent(self):
        with patch.object(sarvam_translate, "dotenv_values", return_value={"SARVAM_API_KEY": None}):
            with self.assertRaises(ValueError):
                sarvam_translate.translate_text("Test text", "hi-IN")
        self.client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
