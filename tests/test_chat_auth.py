"""ChatServicer token extraction (D-27): Bearer header, request field, or cookie + CSRF header.
    python tests/test_chat_auth.py
"""
import os, sys, types
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
_hd = types.ModuleType("src.hybrid_detect"); _hd.HybridDetector = object; sys.modules["src.hybrid_detect"] = _hd  # no torch
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/tux-chat-auth-test.db")
from api.grpc.chat_servicer import _token_from_metadata as t

assert t({"authorization": "Bearer abc"}) == "abc"
assert t({}, "fromfield") == "fromfield"
cookie = "access_token=jwt123; csrf_token=c5rf; refresh_token=r"
assert t({"cookie": cookie, "x-csrf-token": "c5rf"}) == "jwt123"           # browser
assert t({"cookie": cookie}) == ""                                             # no CSRF header
assert t({"cookie": cookie, "x-csrf-token": "wrong"}) == ""                    # wrong CSRF header
assert t({"cookie": "access_token=jwt123", "x-csrf-token": ""}) == ""          # no CSRF cookie
assert t({"authorization": "Bearer ", "cookie": cookie, "x-csrf-token": "c5rf"}) == "jwt123"
print("chat auth: ok")
