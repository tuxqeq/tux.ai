"""RAG retriever (api/services/rag.py, thesis decision log D-23).

Runs without torch, Ollama, PostgreSQL or Redis: SQLite (aiosqlite), fakeredis and a hashing
embedding stand in for them. Needs: chromadb fakeredis aiosqlite sqlalchemy presidio-anonymizer faker.
    python tests/test_rag.py
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

import uuid

from fake_embedding import FakeEF
import api.services.rag as rag
corpus = """HEALTHCARE PROFESSIONAL PROFILE
==========
Dr. [PERSON_aaaaaaaaaaaa], SSN: [SSN_111111111111]
Department: Cardiology. Email: [EMAIL_121212121212]
==========
TECH STARTUP EMPLOYEE
==========
Engineer [PERSON_bbbbbbbbbbbb], SSN: [SSN_222222222222]
Team: backend payments. Login: [USERNAME_232323232323]
==========
Banking customer [PERSON_cccccccccccc] with account [BANK_333333333333] at branch downtown
=========="""
recs = rag.split_records(corpus)
assert len(recs) == 3 and all("[PERSON_" in r for r in recs), recs
db = tempfile.mkdtemp(); ds = uuid.uuid4()
R = rag.Retriever(db, embedding_function=FakeEF())
st = R.add_records(ds, [{"id": f"doc{i}", "text": t, "metadata": {"source": f"doc{i}"}} for i, t in enumerate(recs)])
assert st["records"] == 3 and st["collection"] == 3 + st["chunks"], st
r1 = R.retrieve(ds, "What is the SSN of [PERSON_bbbbbbbbbbbb]?", k=2)
assert r1[0]["id"] == "doc1" and r1[0]["match"] == "token", r1
r2 = R.retrieve(ds, "Who works in cardiology department?", k=1)
assert r2 and r2[0]["id"] == "doc0" and r2[0]["match"] == "semantic", r2
r3 = R.retrieve(ds, "Compare [PERSON_aaaaaaaaaaaa] and [PERSON_cccccccccccc]", k=3)
assert {x["id"] for x in r3 if x["match"] == "token"} == {"doc0", "doc2"}, r3
assert R.retrieve(uuid.uuid4(), "anything", 3) == []          # other dataset: no collection, nothing crosses datasets
n0 = R.collection(ds).count()
assert R.retrieve(ds, "", 3) == []; R.add_records(ds, [{"id": "doc0", "text": recs[0], "metadata": {"source": "doc0"}}]); assert R.collection(ds).count() == n0   # upsert is idempotent
p = rag.build_system_prompt(r1)
assert "[SSN_222222222222]" in p and "copy its token exactly" in p
assert rag.token_ids("about PERSON_bbbbbbbbbbbb and [SSN_111111111111], not x_PERSON_cc or deadbeef12") == ["bbbbbbbbbbbb", "111111111111"]
r4 = R.retrieve(ds, "What is the SSN of PERSON_bbbbbbbbbbbb", k=1)
assert r4[0]["id"] == "doc1" and r4[0]["match"] == "token"
assert R.has_index(ds) and not R.has_index(uuid.uuid4())
d = tempfile.mkdtemp()
open(os.path.join(d, "doc_0001.txt"), "w").write(corpus); open(os.path.join(d, "notes.md"), "w").write("x")
recs2 = rag.records_from_dir(d)
assert [r["id"] for r in recs2] == ["doc_0001#0", "doc_0001#1", "doc_0001#2"] and recs2[1]["metadata"] == {"source": "doc_0001.txt", "record": 1}
assert "(no matching records)" in rag.build_system_prompt([])
# a long record: the answer is in a late section that the record-level embedding would cut off
long_rec = ("Record: Government Contractor\nName: [PERSON_dddddddddddd]\nSSN: [SSN_444444444444]\n\n"
            + "\n\n".join(f"Section {n}:\n- Field {n}: [ID_{n:012x}] value text filler words" for n in range(30))
            + "\n\nMedical (VA Records):\n- Treatment at: Fort Belvoir Community Hospital oncology ward")
R.add_records(ds, [{"id": "long#0", "text": long_rec, "metadata": {"source": "long.txt"}}])
r5 = R.retrieve(ds, "Who had treatment at Fort Belvoir Community Hospital?", k=1)
assert r5 and r5[0]["id"] == "long#0" and r5[0]["text"] == long_rec, r5   # whole parent record returned
assert rag.split_sections("Title\n\nA: 1\n\nName: [PERSON_aaaaaaaaaaaa] lives here and there") == ["Title\nA: 1\nName: [PERSON_aaaaaaaaaaaa] lives here and there"]
R.reset(ds); assert not R.has_index(ds)
real = rag.records_from_dir(synthetic_raw_docs(3))   # generate_synthetic_docs output format (seed 42, 3 files)
assert len(real) == 3 and all("Record:" in r["text"] for r in real), [r["text"][:30] for r in real]
secs = rag.split_sections(real[0]["text"]); print("real record:", len(real[0]["text"]), "chars,", len(secs), "sections")
print("rag retriever: ok")
