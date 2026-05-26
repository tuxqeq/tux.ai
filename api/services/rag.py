"""
RAG retriever — embeds a query and returns the top-k matching tokenized record
chunks from ChromaDB.

Thread-safe lazy init: the sentence-transformer model and ChromaDB client are
loaded once on first call, not at import time (keeps startup fast).
"""

import os
import threading
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.path.join(_ROOT, "chroma_db")
COLLECTION_NAME = "tokenized_records"

_lock = threading.Lock()
_collection = None
_ef = None


def _init(db_path: str) -> None:
    global _collection, _ef
    import chromadb
    from chromadb.utils import embedding_functions

    _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=db_path)
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )


def retrieve(
    query: str,
    n_results: int = 3,
    db_path: Optional[str] = None,
) -> str:
    """
    Return the top-n matching record chunks as a formatted context string.
    Returns empty string if ChromaDB is unavailable or the collection is empty.
    """
    global _collection
    if not query.strip():
        return ""

    path = db_path or os.environ.get("CHROMA_DB_PATH", DEFAULT_DB_PATH)
    if not os.path.isdir(path):
        return ""

    try:
        with _lock:
            if _collection is None:
                _init(path)

        if _collection.count() == 0:
            return ""

        results = _collection.query(
            query_texts=[query],
            n_results=min(n_results, _collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return ""

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not docs:
        return ""

    parts = []
    for doc, meta, dist in zip(docs, metas, distances):
        similarity = 1.0 - dist
        if similarity < 0.15:
            continue
        record_type = meta.get("record_type", "record")
        parts.append(f"[Retrieved {record_type} record (relevance {similarity:.2f})]:\n{doc}")

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
