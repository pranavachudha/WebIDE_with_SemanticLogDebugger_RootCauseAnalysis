import hashlib
import math
import os
import re
from functools import lru_cache


EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def _load_model():
    """Load MiniLM lazily so API startup stays responsive."""
    if os.getenv("SEMANTIC_DEBUGGER_EMBEDDER", "hash").lower() != "minilm":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        return None


def _hash_embedding(text: str) -> list[float]:
    """Deterministic local fallback when transformer weights are unavailable."""
    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s]", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def generate_embedding(text: str) -> list[float]:
    """Generate a dense semantic vector using MiniLM with a deterministic fallback."""
    if not text:
        return [0.0] * EMBEDDING_DIMENSION

    model = _load_model()
    if model is None:
        return _hash_embedding(text)

    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()
