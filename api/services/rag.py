"""
rag.py — dataset-scoped retrieval of tokenized records (ChromaDB).

Thesis decision log D-23. One Chroma collection per dataset ("ds_<dataset uuid hex>"). Personal
data in the records is already replaced by tokens, so nothing here (index, embeddings, prompt)
sees plaintext PII.

The collection holds two kinds of documents:
  kind=record  one whole record (a corpus file has 1+ records between "====" lines)
  kind=chunk   one section of a record (split on blank lines), with metadata parent=<record id>
all-MiniLM-L6-v2 reads at most 256 word pieces, and a record is longer than that (tokens such as
[PERSON_1a2b3c4d5e6f] alone are ~10 word pieces), so the embedding of a whole record misses its
later sections. Sections are embedded; the whole parent record goes into the prompt.

retrieve(dataset_id, query, k)
  1. token match: records that contain a token id from the (tokenized) question. Token ids are
     keyed and deterministic per dataset (D-20), so "[PERSON_x]" in a question has the same id as
     in the records; this finds the right person when embeddings cannot.
  2. semantic: the best-matching sections; their parent records fill the remaining slots.
"""
import os
import re
import threading
import uuid
from typing import Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# brackets optional: the chat input sanitizer strips "[" and "]", so a token the user pastes
# arrives as PERSON_1a2b3c4d5e6f
_TOKEN_ID_RE = re.compile(r"(?<![A-Za-z0-9])\[?[A-Z][A-Z_]{0,29}_([0-9a-f]{8,16})\]?(?![0-9a-f])")
_RECORD_SEPARATOR = re.compile(r"^={4,}\s*$", re.MULTILINE)
_SECTION_SEPARATOR = re.compile(r"\n\s*\n")
MIN_SIMILARITY = 0.15

SYSTEM_PROMPT = """You answer questions about the records below. Personal data in the records is \
replaced by tokens such as [PERSON_1a2b3c4d5e6f]. Rules:
1. Use only the records below. If they do not contain the answer, say that you cannot find it.
2. When you refer to personal data, copy its token exactly, character for character.
3. Never invent a token and never guess the real value behind a token.
4. Answer briefly. /no_think

Records:
{context}"""


def collection_name(dataset_id) -> str:
    return f"ds_{uuid.UUID(str(dataset_id)).hex}"


def token_ids(text: str) -> List[str]:
    return list(dict.fromkeys(_TOKEN_ID_RE.findall(text or "")))


def split_records(text: str, min_chars: int = 40) -> List[str]:
    """Split a tokenized corpus file into records on lines of ==== (generate_synthetic_docs format).
    Parts shorter than min_chars (the file title) are dropped."""
    parts = [p.strip() for p in _RECORD_SEPARATOR.split(text)]
    return [p for p in parts if len(p) >= min_chars]


def split_sections(record: str, min_chars: int = 40) -> List[str]:
    """Split a record on blank lines; a section shorter than min_chars is joined to the next one."""
    out: List[str] = []
    carry = ""
    for part in (p.strip() for p in _SECTION_SEPARATOR.split(record)):
        if not part:
            continue
        part = f"{carry}\n{part}" if carry else part
        if len(part) < min_chars:
            carry = part
            continue
        out.append(part)
        carry = ""
    if carry:
        if out:
            out[-1] = f"{out[-1]}\n{carry}"
        else:
            out.append(carry)
    return out


def records_from_dir(corpus_dir: str) -> List[Dict]:
    """All records of a tokenized corpus directory: [{"id": "<file stem>#<n>", "text", "metadata"}]."""
    out: List[Dict] = []
    for fname in sorted(f for f in os.listdir(corpus_dir) if f.endswith(".txt")):
        with open(os.path.join(corpus_dir, fname), encoding="utf-8") as f:
            text = f.read()
        stem = os.path.splitext(fname)[0]
        for i, rec in enumerate(split_records(text)):
            out.append({"id": f"{stem}#{i}", "text": rec, "metadata": {"source": fname, "record": i}})
    return out


def _default_embedding_function():
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


class Retriever:
    def __init__(self, db_path: str, embedding_function=None):
        self.db_path = db_path if os.path.isabs(db_path) else os.path.join(_ROOT, db_path)
        self._ef = embedding_function
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                import chromadb
                os.makedirs(self.db_path, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.db_path)
                if self._ef is None:
                    self._ef = _default_embedding_function()
            return self._client

    def collection(self, dataset_id, create: bool = False):
        client = self._get_client()
        name = collection_name(dataset_id)
        if create:
            return client.get_or_create_collection(name=name, embedding_function=self._ef,
                                                   metadata={"hnsw:space": "cosine"})
        try:
            return client.get_collection(name=name, embedding_function=self._ef)
        except Exception:
            return None

    def has_index(self, dataset_id) -> bool:
        col = self.collection(dataset_id)
        return col is not None and col.count() > 0

    def reset(self, dataset_id) -> None:
        try:
            self._get_client().delete_collection(collection_name(dataset_id))
        except Exception:
            pass

    def add_records(self, dataset_id, records: List[Dict], batch_size: int = 256) -> Dict[str, int]:
        """records: [{"id", "text", "metadata"}]. Upserts each record and its sections."""
        col = self.collection(dataset_id, create=True)
        docs = []
        for r in records:
            meta = dict(r.get("metadata") or {})
            docs.append((r["id"], r["text"], {**meta, "kind": "record"}))
            for j, sec in enumerate(split_sections(r["text"])):
                docs.append((f"{r['id']}/{j}", sec, {**meta, "kind": "chunk", "parent": r["id"]}))
        for i in range(0, len(docs), batch_size):
            b = docs[i:i + batch_size]
            col.upsert(ids=[d[0] for d in b], documents=[d[1] for d in b], metadatas=[d[2] for d in b])
        return {"records": len(records), "chunks": len(docs) - len(records), "collection": col.count()}

    def retrieve(self, dataset_id, query: str, k: int = 3, context: str = "") -> List[Dict]:
        """Return up to k whole records: [{"id", "text", "match": "token"|"semantic", "score"}].

        context: earlier turns of the chat (tokenized). Their token ids also select records, ranked
        below the ids of the question itself, so a follow-up such as "And her date of birth?"
        still finds the record of the person asked about before (D-29).
        """
        if not query or not query.strip() or k <= 0:
            return []
        col = self.collection(dataset_id)
        if col is None or col.count() == 0:
            return []
        out: List[Dict] = []
        q_ids = token_ids(query)
        c_ids = [t for t in token_ids(context) if t not in q_ids]
        ids = q_ids + c_ids
        if ids:
            where_doc = {"$contains": ids[0]} if len(ids) == 1 else {"$or": [{"$contains": t} for t in ids]}
            got = col.get(where={"kind": "record"}, where_document=where_doc, include=["documents"])

            def score(doc: str) -> float:
                return 10.0 * sum(t in doc for t in q_ids) + sum(t in doc for t in c_ids)

            hits = sorted(zip(got["ids"], got["documents"]), key=lambda x: (-score(x[1]), x[0]))
            out = [{"id": i, "text": d, "match": "token", "score": score(d)} for i, d in hits[:k]]
        if len(out) < k:
            seen = {r["id"] for r in out}
            res = col.query(query_texts=[query], n_results=min(4 * k + len(seen), col.count()),
                            where={"kind": "chunk"}, include=["metadatas", "distances"])
            parents: List[tuple] = []
            for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
                pid, sim = meta.get("parent"), 1.0 - dist
                if not pid or pid in seen or sim < MIN_SIMILARITY:
                    continue
                seen.add(pid)
                parents.append((pid, sim))
                if len(out) + len(parents) >= k:
                    break
            if parents:
                got = col.get(ids=[p for p, _ in parents], include=["documents"])
                text_of = dict(zip(got["ids"], got["documents"]))
                out += [{"id": p, "text": text_of[p], "match": "semantic", "score": s}
                        for p, s in parents if p in text_of]
        return out


def build_system_prompt(records: List[Dict]) -> str:
    context = "\n\n---\n\n".join(r["text"] for r in records) or "(no matching records)"
    return SYSTEM_PROMPT.format(context=context)


_default: Optional[Retriever] = None
_default_lock = threading.Lock()


def get_retriever() -> Retriever:
    global _default
    with _default_lock:
        if _default is None:
            from api.config import get_settings
            _default = Retriever(get_settings().CHROMA_DB_PATH)
        return _default


def context_for_chat(dataset_id, query: str, k: int = 3, context: str = "") -> Optional[List[Dict]]:
    """Chat path helper. None = this dataset has no RAG index (chat runs without RAG);
    a list (possibly empty) = records to put in the system prompt. Never raises."""
    try:
        r = get_retriever()
        if not r.has_index(dataset_id):
            return None
        return r.retrieve(dataset_id, query, k, context)
    except Exception:
        import logging
        logging.getLogger("tuxai").exception("RAG retrieval failed")
        return None
