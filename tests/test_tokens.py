"""Token-map value cipher (D-22) and possessive trimming (D-24).

Runs without torch, Ollama, PostgreSQL or Redis: SQLite (aiosqlite), fakeredis and a hashing
embedding stand in for them. Needs: chromadb fakeredis aiosqlite sqlalchemy presidio-anonymizer faker.
    python tests/test_tokens.py
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

def test_value_cipher():
    import base64
    from presidio_anonymizer import AnonymizerEngine, DeanonymizeEngine
    from presidio_anonymizer.entities import OperatorConfig, RecognizerResult
    from utils import encrypt_value, decrypt_value
    def old_encrypt(key, v):   # the pre-v2 path (pseudonymize._encrypt_value before 2026-11-08)
        r = [RecognizerResult(entity_type="PII", start=0, end=len(v), score=1.0)]
        return AnonymizerEngine().anonymize(text=v, analyzer_results=r,
            operators={"DEFAULT": OperatorConfig("encrypt", {"key": base64.b64encode(key).decode()})}).text
    def old_decrypt(key, blob):
        r = [RecognizerResult(entity_type="PII", start=0, end=len(blob), score=1.0)]
        return DeanonymizeEngine().deanonymize(text=blob, entities=r,
            operators={"DEFAULT": OperatorConfig("decrypt", {"key": base64.b64encode(key).decode()})}).text
    v = "John Smith — 123-45-6789"
    for n in (16, 24):
        k = os.urandom(n)
        assert decrypt_value(k, old_encrypt(k, v)) == v and old_decrypt(k, encrypt_value(k, v)) == v
    k32 = os.urandom(32)
    try:
        old_encrypt(k32, v); print("old path worked with 32 bytes?!")
    except Exception as e:
        print("old path with a 32-byte key fails:", type(e).__name__)
    assert decrypt_value(k32, encrypt_value(k32, v)) == v
    assert encrypt_value(k32, v) != encrypt_value(k32, v)   # random IV
    from pseudonymize import PIIPseudonymizer
    p = PIIPseudonymizer(k32)
    t, m = p.pseudonymize("Patient John Smith", [{"start": 8, "end": 18, "label": "PERSON", "text": "John Smith", "source": "AI_MODEL", "score": 1.0}])
    tok = next(iter(m)); assert decrypt_value(k32, m[tok]) == "John Smith"
    from api.services.decryptor import resolve_tokens
    assert resolve_tokens(t, m, k32, {"*"}) == "Patient John Smith", resolve_tokens(t, m, k32, {"*"})
    assert resolve_tokens(t, m, k32, set()) == t
    print("cipher: 16/24-byte keys compatible both ways; 32-byte keys work; pseudonymizer -> API decryptor round trip ok")


def test_possessive():
    from pseudonymize import PIIPseudonymizer, token_id
    key = os.urandom(32)
    p = PIIPseudonymizer(key)
    q = "What is John Smith's SSN? Ask Mary Jones’s team and O's office."
    dets = [{"start": 8, "end": 20, "label": "PERSON", "text": "John Smith's", "source": "AI_MODEL", "score": 1.0},
            {"start": 30, "end": 42, "label": "PERSON", "text": "Mary Jones’s", "source": "AI_MODEL", "score": 1.0},
            {"start": 52, "end": 55, "label": "PERSON", "text": "O's", "source": "AI_MODEL", "score": 1.0}]
    assert q[8:20] == "John Smith's" and q[30:42] == "Mary Jones’s" and q[52:55] == "O's", (q[8:20], q[30:42], q[52:55])
    out, m = p.pseudonymize(q, dets)
    tid = token_id(key, "John Smith"); tid2 = token_id(key, "Mary Jones")
    assert f"[PERSON_{tid}]'s SSN" in out, out
    assert f"[PERSON_{tid2}]’s team" in out, out
    assert "O's" not in out, out   # a 3-char value is tokenized whole
    print(out)
    p2 = PIIPseudonymizer(key)
    out2, _ = p2.pseudonymize("Patient: John Smith", [{"start": 9, "end": 19, "label": "PERSON", "text": "John Smith", "source": "AI_MODEL", "score": 1.0}])
    assert f"[PERSON_{tid}]" in out2
    print("possessive: ok (question and record get the same token)")


if __name__ == "__main__":
    test_value_cipher()
    test_possessive()
