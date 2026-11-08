#!/usr/bin/env python3
"""
bootstrap_dataset.py — register a tokenized corpus as a chat dataset (thesis decision log D-23).

Run it on the machine that runs the API (the RunPod pod), after llm/prepare_corpus.py has written
the corpus and its token maps into the SAME Redis, and after `alembic upgrade head`:

  1. PostgreSQL: a Dataset row and its AES key, wrapped with MASTER_KEY (EncryptionKey)
  2. Redis: every tokenmap:{file stem} of the corpus -> ds:{dataset_id}:tokenmap (no expiry);
     a map whose keyref fingerprint is not the fingerprint of --key-file stops the script
  3. Chroma (CHROMA_DB_PATH): collection ds_<dataset id> with the records and their sections

  python scripts/bootstrap_dataset.py --name "Synthetic corpus v2" --model qwen3:4b
  python scripts/bootstrap_dataset.py --dataset-id <uuid> --reindex     # rebuild the index only

Restart the API after a rebuild: Chroma's PersistentClient is not safe across processes.
"""
import argparse
import asyncio
import base64
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_CORPUS = os.path.join(ROOT, "llm", "data", "tokenized_v2")
DEFAULT_KEY_FILE = os.path.join(ROOT, "llm", "data", "dataset_key.b64")


def read_key(key_file: str) -> bytes:
    if not os.path.exists(key_file):
        sys.exit(f"ERROR: key file not found: {key_file} (llm/prepare_corpus.py creates it)")
    key = base64.b64decode(open(key_file).read().strip())
    if len(key) not in (16, 24, 32):
        sys.exit(f"ERROR: the key in {key_file} has {len(key)} bytes; expected 16, 24 or 32")
    return key


def corpus_stems(corpus_dir: str) -> list:
    if not os.path.isdir(corpus_dir):
        sys.exit(f"ERROR: corpus directory not found: {corpus_dir}")
    stems = sorted(os.path.splitext(f)[0] for f in os.listdir(corpus_dir) if f.endswith(".txt"))
    if not stems:
        sys.exit(f"ERROR: no .txt files in {corpus_dir}")
    return stems


def check_token_maps(r, stems: list, fingerprint: str) -> dict:
    """Read-only check of the corpus maps in Redis. Returns {"found", "missing", "wrong_key"}."""
    found, missing, wrong = [], [], []
    for stem in stems:
        if not r.exists(f"tokenmap:{stem}"):
            missing.append(stem)  # also normal for a file without any PII
            continue
        if r.hget(f"keyref:{stem}", "key_id") != fingerprint:
            wrong.append(stem)
            continue
        found.append(stem)
    return {"found": found, "missing": missing, "wrong_key": wrong}


def copy_token_maps(r, dataset_id, stems: list) -> int:
    """tokenmap:{stem} -> ds:{dataset_id}:tokenmap, without expiry. Returns the map size."""
    target = f"ds:{dataset_id}:tokenmap"
    for stem in stems:
        m = r.hgetall(f"tokenmap:{stem}")
        if m:
            r.hset(target, mapping=m)
    r.persist(target)
    return r.hlen(target)


async def ensure_dataset(session_factory, key: bytes, dataset_id, name, description, model,
                         admin_email) -> tuple:
    """Create the dataset (or load it) and store its key. Returns (dataset_id, created)."""
    from sqlalchemy import select
    from api.models import Dataset, EncryptionKey, User
    from api.security import decrypt_aes_key, encrypt_aes_key, key_ref

    async with session_factory() as db:
        created = False
        admin = (await db.execute(select(User).where(User.email == admin_email))).scalar_one_or_none()
        if dataset_id:
            ds = await db.get(Dataset, uuid.UUID(str(dataset_id)))
            if ds is None:
                # PostgreSQL on a RunPod pod lives on the container disk and is empty after a restart,
                # while Redis (dump.rdb), the corpus and the Chroma index live on /workspace and are keyed
                # by this id: re-create the row with the same id.
                ds = Dataset(id=uuid.UUID(str(dataset_id)), name=name, description=description,
                             created_by=admin.id if admin else None)
                db.add(ds)
                await db.flush()
                created = True
        else:
            ds = Dataset(name=name, description=description, created_by=admin.id if admin else None)
            db.add(ds)
            await db.flush()
            created = True
        if model:
            ds.model_name = model

        existing = (await db.execute(
            select(EncryptionKey).where(EncryptionKey.dataset_id == ds.id))).scalar_one_or_none()
        if existing is None:
            db.add(EncryptionKey(dataset_id=ds.id, encrypted_key=encrypt_aes_key(key),
                                 key_ref=key_ref(key), created_by=ds.created_by))
        elif decrypt_aes_key(existing.encrypted_key) != key:
            sys.exit(f"ERROR: dataset {ds.id} already has a different key")
        await db.commit()
        return ds.id, created


async def mark_imported(session_factory, dataset_id) -> None:
    from api.models import Dataset
    async with session_factory() as db:
        ds = await db.get(Dataset, uuid.UUID(str(dataset_id)))
        ds.rdb_imported = True
        await db.commit()


def build_index(retriever, dataset_id, corpus_dir: str, reset: bool) -> dict:
    from api.services import rag
    if reset:
        retriever.reset(dataset_id)
    records = rag.records_from_dir(corpus_dir)
    return retriever.add_records(dataset_id, records)


async def main_async(args, session_factory=None, redis_client=None, retriever=None) -> uuid.UUID:
    from api.config import get_settings
    from llm.prepare_corpus import key_fingerprint
    settings = get_settings()

    key = read_key(args.key_file)
    stems = corpus_stems(args.corpus_dir)

    if redis_client is None:
        import redis
        redis_client = redis.from_url(args.redis_url or settings.REDIS_URL, decode_responses=True)
    if session_factory is None:
        from api.db import AsyncSessionLocal as session_factory
    if retriever is None:
        from api.services.rag import Retriever
        retriever = Retriever(settings.CHROMA_DB_PATH)

    check = check_token_maps(redis_client, stems, key_fingerprint(key))
    print(f"Corpus: {len(stems)} files in {args.corpus_dir}")
    print(f"Token maps in Redis: {len(check['found'])} ok, {len(check['missing'])} missing, "
          f"{len(check['wrong_key'])} made with another key")
    if check["wrong_key"]:
        sys.exit("ERROR: some maps were made with another key (e.g. " + ", ".join(check["wrong_key"][:3])
                 + "). Use the --key-file that prepare_corpus.py used.")
    if not check["found"] and not args.reindex:
        sys.exit("ERROR: no token maps of this corpus in Redis. Run llm/prepare_corpus.py with this Redis first.")

    dataset_id, created = await ensure_dataset(session_factory, key, args.dataset_id, args.name,
                                               args.description, args.model, args.admin_email)
    print(f"Dataset {'created' if created else 'found'}: {dataset_id}")

    if not args.reindex:
        n = copy_token_maps(redis_client, dataset_id, check["found"])
        await mark_imported(session_factory, dataset_id)
        print(f"Token map ds:{dataset_id}:tokenmap: {n} tokens (no expiry)")

    stats = build_index(retriever, dataset_id, args.corpus_dir, reset=True)  # idempotent: always rebuild
    print(f"RAG index {retriever.db_path} / ds_{uuid.UUID(str(dataset_id)).hex}: "
          f"{stats['records']} records, {stats['chunks']} sections")
    print(f"\nDATASET_ID={dataset_id}")
    return dataset_id


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", default=DEFAULT_CORPUS)
    ap.add_argument("--key-file", default=DEFAULT_KEY_FILE)
    ap.add_argument("--dataset-id", default=None, help="use an existing dataset instead of creating one")
    ap.add_argument("--name", default="Synthetic corpus v2")
    ap.add_argument("--description", default="generate_synthetic_docs.py (seed 42), tokenized with detector v4")
    ap.add_argument("--model", default="qwen3:4b",
                    help="Ollama model for this dataset's chats (Dataset.model_name); '' keeps the current one")
    ap.add_argument("--admin-email", default="admin@tux.ai")
    ap.add_argument("--redis-url", default=None)
    ap.add_argument("--reindex", action="store_true",
                    help="only rebuild the Chroma index (needs --dataset-id)")
    args = ap.parse_args(argv)
    if args.reindex and not args.dataset_id:
        ap.error("--reindex needs --dataset-id")
    return args


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))
