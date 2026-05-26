"""
build_rag_index.py — Index tokenized records into ChromaDB for RAG retrieval.

Reads all .txt files from the output directory, splits them into per-record
chunks, embeds with sentence-transformers/all-MiniLM-L6-v2, and stores in a
persistent ChromaDB collection.

Usage:
    python llm/build_rag_index.py
    python llm/build_rag_index.py --source output/ --db chroma_db/ --reset
"""

import argparse
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = os.path.join(_REPO_ROOT, "output")
DEFAULT_DB = os.path.join(_REPO_ROOT, "chroma_db")
COLLECTION_NAME = "tokenized_records"
RECORD_SEPARATOR = re.compile(r"={4,}")


def _split_records(text: str) -> list[str]:
    """Split a .txt file into individual record chunks on === separators."""
    chunks = RECORD_SEPARATOR.split(text)
    return [c.strip() for c in chunks if c.strip() and len(c.strip()) > 40]


def _collect_files(source_dir: str) -> list[str]:
    paths = []
    for fname in os.listdir(source_dir):
        if fname.endswith(".txt"):
            paths.append(os.path.join(source_dir, fname))
    return paths


def _infer_record_type(chunk: str) -> str:
    first_line = chunk.splitlines()[0].upper() if chunk else ""
    for keyword in ("HEALTHCARE", "BANKING", "BUSINESS", "GOVERNMENT", "TECH"):
        if keyword in first_line:
            return keyword.lower()
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Index tokenized records into ChromaDB.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Directory with tokenized .txt files")
    parser.add_argument("--db", default=DEFAULT_DB, help="ChromaDB persist directory")
    parser.add_argument("--reset", action="store_true", help="Delete existing collection before indexing")
    args = parser.parse_args()

    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("chromadb not installed. Run: pip install chromadb sentence-transformers")
        sys.exit(1)

    if not os.path.isdir(args.source):
        print(f"Source directory not found: {args.source}")
        sys.exit(1)

    files = _collect_files(args.source)
    if not files:
        print(f"No .txt files found in {args.source}")
        sys.exit(1)

    print(f"Found {len(files)} file(s) in {args.source}")

    client = chromadb.PersistentClient(path=args.db)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    if args.reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection '{COLLECTION_NAME}'")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    existing_count = collection.count()
    print(f"Existing documents in collection: {existing_count}")

    docs, ids, metas = [], [], []
    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, encoding="utf-8", errors="replace") as f:
            text = f.read()

        chunks = _split_records(text)
        for i, chunk in enumerate(chunks):
            doc_id = f"{fname}_{i}"
            if existing_count > 0:
                existing = collection.get(ids=[doc_id])
                if existing["ids"]:
                    continue
            docs.append(chunk)
            ids.append(doc_id)
            metas.append({"source": fname, "chunk_index": i, "record_type": _infer_record_type(chunk)})

    if not docs:
        print("No new documents to index.")
        return

    batch_size = 100
    for i in range(0, len(docs), batch_size):
        collection.add(
            documents=docs[i : i + batch_size],
            ids=ids[i : i + batch_size],
            metadatas=metas[i : i + batch_size],
        )
        print(f"  Indexed {min(i + batch_size, len(docs))}/{len(docs)} chunks...")

    print(f"\nDone. Collection '{COLLECTION_NAME}' now has {collection.count()} documents.")
    print(f"ChromaDB stored at: {args.db}")


if __name__ == "__main__":
    main()
