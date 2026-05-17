import json
import os
import numpy as np
from embeddings.generator import generate_embedding

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON_DB_PATH = os.path.join(BACKEND_DIR, "chroma_data.json")
CHROMA_PATH = os.path.join(BACKEND_DIR, "chroma")


def _safe_metadata(metadata: dict) -> dict:
    return {
        key: json.dumps(value) if isinstance(value, (dict, list)) else ("" if value is None else value)
        for key, value in metadata.items()
    }

class SimpleVectorStore:
    def __init__(self):
        self.embeddings = []
        self.metadatas = []
        self.ids = []
        self._load()
        
    def _load(self):
        if os.path.exists(JSON_DB_PATH):
            try:
                with open(JSON_DB_PATH, 'r', encoding="utf-8") as f:
                    data = json.load(f)
                    self.embeddings = data.get("embeddings", [])
                    self.metadatas = data.get("metadatas", [])
                    self.ids = data.get("ids", [])
            except Exception:
                pass
                
    def _save(self):
        with open(JSON_DB_PATH, 'w', encoding="utf-8") as f:
            json.dump({
                "embeddings": self.embeddings,
                "metadatas": self.metadatas,
                "ids": self.ids
            }, f)
            
    def add(self, ids, embeddings, metadatas):
        for idx, emb, meta in zip(ids, embeddings, metadatas):
            if idx in self.ids:
                i = self.ids.index(idx)
                self.embeddings[i] = emb
                self.metadatas[i] = meta
            else:
                self.ids.append(idx)
                self.embeddings.append(emb)
                self.metadatas.append(meta)
        self._save()
        
    def query(self, query_embeddings, n_results=3):
        if not self.embeddings:
            return {"ids": [[]], "distances": [[]], "metadatas": [[]]}
            
        q_emb = np.array(query_embeddings)
        db_emb = np.array(self.embeddings)
        
        q_norm = np.linalg.norm(q_emb, axis=1, keepdims=True)
        db_norm = np.linalg.norm(db_emb, axis=1, keepdims=True).T
        similarities = (q_emb @ db_emb.T / np.maximum(q_norm @ db_norm, 1e-12))[0]
        
        # Sort by similarity descending
        top_indices = np.argsort(similarities)[::-1][:n_results]
        
        return {
            "ids": [[self.ids[i] for i in top_indices]],
            # convert similarity to "distance" where 0 is perfect match
            "distances": [[float(1.0 - similarities[i]) for i in top_indices]], 
            "metadatas": [[self.metadatas[i] for i in top_indices]],
            "embeddings": [[self.embeddings[i] for i in top_indices]],
        }

    def get_all(self):
        return {
            "ids": self.ids,
            "embeddings": self.embeddings,
            "metadatas": self.metadatas,
        }

class ChromaVectorStore:
    def __init__(self):
        try:
            import chromadb

            self.client = chromadb.PersistentClient(path=CHROMA_PATH)
            self.collection = self.client.get_or_create_collection(name="traceback_embeddings")
            self.available = True
        except Exception:
            self.available = False
            self.collection = None

    def add(self, ids, embeddings, metadatas):
        if not self.available:
            raise RuntimeError("ChromaDB is not available")
        self.collection.upsert(ids=ids, embeddings=embeddings, metadatas=[_safe_metadata(m) for m in metadatas])

    def query(self, query_embeddings, n_results=3):
        if not self.available:
            raise RuntimeError("ChromaDB is not available")
        try:
            results = self.collection.query(query_embeddings=query_embeddings, n_results=n_results, include=["embeddings", "metadatas"])
        except TypeError:
            results = self.collection.query(query_embeddings=query_embeddings, n_results=n_results)

        return {
            "ids": results.get("ids", [[]]),
            "distances": results.get("distances", [[]]),
            "metadatas": results.get("metadatas", [[]]),
            "embeddings": results.get("embeddings", [[]]),
        }

    def get_all(self):
        if not self.available:
            raise RuntimeError("ChromaDB is not available")
        try:
            results = self.collection.get(include=["ids", "embeddings", "metadatas"])
        except Exception:
            results = self.collection.get()
        return {
            "ids": results.get("ids", []),
            "embeddings": results.get("embeddings", []),
            "metadatas": results.get("metadatas", []),
        }


_chroma_store = ChromaVectorStore()
traceback_collection = _chroma_store if _chroma_store.available else SimpleVectorStore()

def add_bug_to_db(
    bug_id: str,
    exception_type: str,
    traceback_str: str,
    buggy_code: str,
    fixed_code: str,
    rca_summary: str,
    patch: str = "",
    project: str = "",
    failing_function: str = "",
    imports: list[str] | None = None,
    file_path: str = "",
):
    """Adds a bug into the vector database."""
    text_to_embed = "\n".join(
        [
            exception_type,
            traceback_str,
            failing_function,
            ", ".join(imports or []),
            buggy_code,
            patch,
            rca_summary,
        ]
    )
    embedding = generate_embedding(text_to_embed)
    
    traceback_collection.add(
        ids=[bug_id],
        embeddings=[embedding],
        metadatas=[{
            "bug_id": bug_id,
            "project": project,
            "exception_type": exception_type,
            "rca_summary": rca_summary,
            "buggy_code": buggy_code,
            "fixed_code": fixed_code,
            "patch": patch,
            "failing_function": failing_function,
            "imports": imports or [],
            "file_path": file_path,
            "stack_trace": traceback_str,
        }]
    )

def get_similar_bugs(exception_type: str, traceback_str: str, code: str, top_k: int = 5):
    """Retrieves similar bugs from the database based on the traceback and code."""
    query_text = f"{exception_type}\n{traceback_str}\n{code}"
    query_embedding = generate_embedding(query_text)
    
    results = traceback_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    similar_bugs = []
    if results and results['ids'] and len(results['ids'][0]) > 0:
        embeddings = results.get('embeddings', [[]])[0] if results.get('embeddings') else []
        for i in range(len(results['ids'][0])):
            dist = results['distances'][0][i]
            if dist < 1.25: # Chroma cosine distance can exceed 1 for weak matches.
                bug = {
                    "bug_id": results['ids'][0][i],
                    "score": 1.0 - dist,
                    "metadata": results['metadatas'][0][i],
                    "embedding": embeddings[i] if i < len(embeddings) else None,
                }
                similar_bugs.append(bug)
            
    return similar_bugs
