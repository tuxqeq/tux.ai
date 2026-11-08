"""Deterministic bag-of-words hashing embedding for tests (no model download)."""
import hashlib, math
from chromadb import EmbeddingFunction, Documents, Embeddings
class FakeEF(EmbeddingFunction):
    """bag-of-words hashing embedding (deterministic, no model download)"""
    def __init__(self): pass
    def __call__(self, input: Documents) -> Embeddings:
        out = []
        for doc in input:
            v = [0.0] * 64
            for w in doc.lower().replace(":", " ").split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
    @staticmethod
    def name(): return "fake-bow"
    def get_config(self): return {}
    @staticmethod
    def build_from_config(config): return FakeEF()
