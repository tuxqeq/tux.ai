"""scripts/bootstrap_dataset.py and the RAG chat path of ChatServicer (D-23), end to end.

Runs without torch, Ollama, PostgreSQL or Redis: SQLite (aiosqlite), fakeredis and a hashing
embedding stand in for them. Needs: chromadb fakeredis aiosqlite sqlalchemy presidio-anonymizer faker.
    python tests/test_bootstrap_chat.py
"""
import os, sys, tempfile, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts"), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def synthetic_raw_docs(count: int) -> str:
    """generate_synthetic_docs.py output (seed 42) in a temp dir."""
    d = tempfile.mkdtemp()
    subprocess.run([sys.executable, os.path.join(ROOT, "llm", "generate_synthetic_docs.py"), "--count", str(count),
                    "--seed", "42", "--output-dir", d], check=True, capture_output=True)
    return d

import re, base64, asyncio, uuid, glob
root, raw_dir, work = ROOT, synthetic_raw_docs(15), tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{work}/t.db"
os.environ["CHROMA_DB_PATH"] = f"{work}/chroma"
import fakeredis, redis_client as rc
from fake_embedding import FakeEF
fr = fakeredis.FakeRedis(decode_responses=True)
rc.get_client = lambda url: fr
from pseudonymize import PIIPseudonymizer
from llm.prepare_corpus import key_fingerprint

# --- simulate prepare_corpus (no torch here): regex "detector" for names, SSNs, emails
def detect(text):
    out = []
    for lab, rx in [("PERSON", r"(?<=Name: )[^\n]+|(?<=\nDr\. )[A-Z][a-z]+ [A-Z][a-z]+"), ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"), ("EMAIL", r"[\w.]+@[\w.-]+")]:
        out += [{"start": m.start(), "end": m.end(), "label": lab, "text": m.group(), "source": "T", "score": 1.0} for m in re.finditer(rx, text)]
    return out
key = os.urandom(32); key_file = f"{work}/key.b64"; open(key_file, "w").write(base64.b64encode(key).decode())
corpus = f"{work}/tokenized"; os.makedirs(corpus)
p = PIIPseudonymizer(key); names = {}
for f in sorted(glob.glob(f"{raw_dir}/*.txt")):
    text = open(f).read(); p.reset()
    tok, m = p.pseudonymize(text, detect(text))
    stem = os.path.splitext(os.path.basename(f))[0]
    names[stem] = re.search(r"(?<=Name: )[^\n]+|(?<=\nDr\. )[A-Z][a-z]+ [A-Z][a-z]+", text).group()
    open(f"{corpus}/{stem}.txt", "w").write(tok)
    rc.store_token_map(token_map=p.get_token_map(), session_id=stem, filename=stem + ".txt", key_id=key_fingerprint(key), ttl=None)

import api.services.rag as rag
from api.db import Base, AsyncSessionLocal, engine
import api.models as M
import bootstrap_dataset as B
async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        db.add(M.User(email="admin@tux.ai", hashed_password="x", role="admin")); await db.commit()
    R = rag.Retriever(f"{work}/chroma", embedding_function=FakeEF())
    args = B.parse_args(["--corpus-dir", corpus, "--key-file", key_file])
    ds_id = await B.main_async(args, AsyncSessionLocal, fr, R)

    from sqlalchemy import select
    from api.security import decrypt_aes_key
    async with AsyncSessionLocal() as db:
        ds = await db.get(M.Dataset, ds_id)
        assert ds.model_name == "qwen3:4b-instruct-2507-q4_K_M" and ds.rdb_imported and ds.created_by is not None
        ek = (await db.execute(select(M.EncryptionKey).where(M.EncryptionKey.dataset_id == ds_id))).scalars().all()
        assert len(ek) == 1 and decrypt_aes_key(ek[0].encrypted_key) == key
    dsmap = fr.hgetall(f"ds:{ds_id}:tokenmap")
    union = {}
    for stem in names: union.update(fr.hgetall(f"tokenmap:{stem}"))
    assert set(dsmap) == set(union) and fr.ttl(f"ds:{ds_id}:tokenmap") == -1

    # chat path: the question is tokenized with the dataset key -> token search finds the record
    stem, name = sorted(names.items())[1]
    q = f"What is {name}'s SSN?"
    i = q.index(name)
    qp = PIIPseudonymizer(key)
    qtok, _ = qp.pseudonymize(q, [{"start": i, "end": i + len(name) + 2, "label": "PERSON", "text": name + "'s", "source": "T", "score": 1.0}])
    hits = R.retrieve(ds_id, qtok, 3)
    assert hits[0]["id"] == f"{stem}#0" and hits[0]["match"] == "token", (qtok, hits)
    # the answer the LLM would give, decrypted for an admin through the dataset map
    ssn_tok = re.search(r"SSN: (\[SSN_[0-9a-f]{12}\])", hits[0]["text"]).group(1)
    from api.services.decryptor import resolve_tokens
    plain = resolve_tokens(f"The SSN is {ssn_tok}.", {}, key, {"*"}, dsmap)
    raw_text = open(f"{raw_dir}/{stem}.txt").read()
    assert re.search(r"SSN: (\d{3}-\d{2}-\d{4})", raw_text).group(1) in plain, plain
    assert resolve_tokens(f"The SSN is {ssn_tok}.", {}, key, {"PERSON"}, dsmap) == f"The SSN is {ssn_tok}."   # RBAC

    # rerun on the same dataset: no second key, index rebuilt to the same size
    n_before = R.collection(ds_id).count()
    await B.main_async(B.parse_args(["--corpus-dir", corpus, "--key-file", key_file, "--dataset-id", str(ds_id), "--reindex"]), AsyncSessionLocal, fr, R)
    assert R.collection(ds_id).count() == n_before
    async with AsyncSessionLocal() as db:
        assert len((await db.execute(select(M.EncryptionKey))).scalars().all()) == 1
    # a different key must be refused before anything is written
    other = f"{work}/other.b64"; open(other, "w").write(base64.b64encode(os.urandom(32)).decode())
    try:
        await B.main_async(B.parse_args(["--corpus-dir", corpus, "--key-file", other]), AsyncSessionLocal, fr, R)
        raise AssertionError("wrong key accepted")
    except SystemExit as e:
        assert "another key" in str(e), e
    async with AsyncSessionLocal() as db:
        assert len((await db.execute(select(M.Dataset))).scalars().all()) == 1

    # --- chat path through ChatServicer.StreamChat (Ollama mocked), dataset with a RAG index
    import types; _hd = types.ModuleType("src.hybrid_detect"); _hd.HybridDetector = object; sys.modules["src.hybrid_detect"] = _hd   # no torch here
    import api.grpc.chat_servicer as CS, redis as _redis
    from api.security import create_access_token
    captured = {}
    async def fake_stream(messages, model=None):
        captured["messages"], captured["model"] = messages, model
        for piece in ["The SSN of ", "the person is ", ssn_tok[:7], ssn_tok[7:], "."]:
            yield piece
    CS.stream_chat = fake_stream
    def fake_tokenize(text, aes_key, model_path):
        pp = PIIPseudonymizer(aes_key)
        dets = [{"start": m.start(), "end": m.end(), "label": "PERSON", "text": m.group(), "source": "T", "score": 1.0}
                for m in re.finditer(re.escape(name) + "'s", text)]
        return pp.pseudonymize(text, dets)
    CS.tokenize_message = fake_tokenize
    rag._default = R
    import src.redis_client as _src_rc; _src_rc.get_client = lambda url: fr
    _redis.from_url = lambda *a, **k: fr
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(M.User))).scalars().first()
    class Ctx:
        def invocation_metadata(self): return [("authorization", "Bearer " + create_access_token(str(admin.id)))]
        async def abort(self, code, msg): raise RuntimeError(f"abort {code} {msg}")
    class Req:
        message = q; chat_session_id = ""; dataset_id = str(ds_id); auth_token = ""
    out = [c async for c in CS.ChatServicer().StreamChat(Req(), Ctx())]
    msgs = captured["messages"]
    assert captured["model"] == "qwen3:4b-instruct-2507-q4_K_M"
    assert msgs[0]["role"] == "system" and hits[0]["text"] in msgs[0]["content"], msgs[0]["content"][:300]
    assert msgs[-1] == {"role": "user", "content": qtok}, msgs[-1]
    assert name not in msgs[0]["content"] and name not in msgs[-1]["content"]   # no plaintext reaches the LLM
    async with AsyncSessionLocal() as db:
        stored = [m.content for m in (await db.execute(select(M.Message).order_by(M.Message.created_at))).scalars()]
    assert stored == [qtok, f"The SSN of the person is {ssn_tok}."], stored   # DB keeps tokens only
    # a dataset WITHOUT an index: no RAG system message
    async with AsyncSessionLocal() as db:
        ds2 = M.Dataset(name="no index"); db.add(ds2); await db.commit(); ds2_id = ds2.id
    class Req2(Req): dataset_id = str(ds2_id)
    _ = [c async for c in CS.ChatServicer().StreamChat(Req2(), Ctx())]
    assert all(m["role"] != "system" for m in captured["messages"]), captured["messages"]
    print("chat wiring: ok (system prompt with the token-matched record, tokens only in LLM input and DB)")
    # pod restart: PostgreSQL is empty, Redis / corpus / index are kept -> the same id is re-created
    async with AsyncSessionLocal() as db:
        for model in (M.AuditLog, M.Message, M.ChatSession, M.EncryptionKey, M.Dataset):
            for row in (await db.execute(select(model))).scalars():
                await db.delete(row)
        await db.commit()
    again = await B.main_async(B.parse_args(["--corpus-dir", corpus, "--key-file", key_file, "--dataset-id", str(ds_id)]), AsyncSessionLocal, fr, R)
    assert again == ds_id
    async with AsyncSessionLocal() as db:
        ds = await db.get(M.Dataset, ds_id)
        ek = (await db.execute(select(M.EncryptionKey))).scalars().all()
        assert ds is not None and ds.rdb_imported and len(ek) == 1 and decrypt_aes_key(ek[0].encrypted_key) == key
    assert R.retrieve(ds_id, qtok, 1)[0]["id"] == f"{stem}#0"
    print("re-create after pod restart: ok")
    print("bootstrap: ok —", ds_id, len(dsmap), "tokens,", n_before, "index docs; question:", qtok)
asyncio.run(run())
