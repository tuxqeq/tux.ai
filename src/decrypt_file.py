"""
decrypt_file.py — Restore a tokenized file back to its original PII content.

Reads [LABEL_hexid] tokens from a tokenized file, looks each one up in Redis,
AES-decrypts the encrypted original value, and writes the restored file.
"""

import base64
import os
import re
import sys
from typing import Dict, Tuple

from presidio_anonymizer import DeanonymizeEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

sys.path.insert(0, os.path.dirname(__file__))
import redis_client as rc

TOKEN_RE = re.compile(r'\[[A-Z_]{1,20}_[0-9a-f]{8}\]')

_deanonymizer = DeanonymizeEngine()


def _decrypt_value(encrypted: str, aes_key: bytes) -> str:
    key_b64 = base64.b64encode(aes_key).decode("utf-8")
    fake_result = [RecognizerResult(entity_type="PII", start=0, end=len(encrypted), score=1.0)]
    result = _deanonymizer.deanonymize(
        text=encrypted,
        entities=fake_result,
        operators={"DEFAULT": OperatorConfig("decrypt", {"key": key_b64})},
    )
    return result.text


def decrypt_token_map(
    token_map: Dict[str, str],
    aes_key: bytes,
) -> Tuple[Dict[str, str], list]:
    """
    Decrypt all values in a token map.
    Returns (decrypted_map, failed_tokens).
    """
    decrypted: Dict[str, str] = {}
    failed: list = []
    for token, encrypted in token_map.items():
        try:
            decrypted[token] = _decrypt_value(encrypted, aes_key)
        except Exception:
            failed.append(token)
    return decrypted, failed


def restore_file(
    input_path: str,
    output_path: str,
    session_id: str,
    aes_key: bytes,
    redis_url: str = rc.DEFAULT_REDIS_URL,
) -> Dict:
    """
    Replace all [LABEL_hexid] tokens in input_path with their original values
    and write the result to output_path.

    Returns a summary dict: { restored, missing, failed, output_path }
    """
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    tokens_in_file = set(TOKEN_RE.findall(text))
    if not tokens_in_file:
        return {"restored": 0, "missing": 0, "failed": 0, "output_path": output_path}

    # Fetch only the tokens that appear in this file
    r = rc.get_client(redis_url)
    token_map: Dict[str, str] = {}
    missing: list = []
    for token in tokens_in_file:
        encrypted = r.hget(f"tokenmap:{session_id}", token)
        if encrypted:
            token_map[token] = encrypted
        else:
            missing.append(token)

    decrypted_map, failed = decrypt_token_map(token_map, aes_key)

    restored_text = text
    for token, original in decrypted_map.items():
        restored_text = restored_text.replace(token, original)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(restored_text)

    return {
        "restored":    len(decrypted_map),
        "missing":     len(missing),
        "failed":      len(failed),
        "output_path": output_path,
        "missing_tokens": missing,
        "failed_tokens":  failed,
    }
