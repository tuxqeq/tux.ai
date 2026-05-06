"""
tokenize_file.py — Replace PII in any text file with readable tokens.

Each detected PII value is replaced with a token like [PERSON_a1b2c3d4].
A companion JSON map stores { token -> AES-encrypted original value } for
later recovery.  Works with .txt files and .json training datasets.

Usage:
    # Uses all defaults — no flags required beyond --input
    python src/tokenize_file.py --input data/train_data.json

    python src/tokenize_file.py --input corpus.txt --key "32ByteSecureKeyForAES256!!!!!!!!"
    python src/tokenize_file.py --input data/train_data.json --no-ai --model-path models/pii_model_large
"""

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_AES_KEY    = "16ByteSecureKey!"          # 16-byte AES-128 key
DEFAULT_MODEL_PATH = "models/pii_model_v2" # pre-trained PII model
# ──────────────────────────────────────────────────────────────────────────────

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from typing import Any, Dict, List

from tqdm import tqdm

# Allow running from repo root or from src/
sys.path.insert(0, os.path.dirname(__file__))

import redis_client as rc

# HybridDetector and PIIPseudonymizer are imported lazily inside process_file()
# so the script can print status messages before the slow transformers import.


# ---------------------------------------------------------------------------
# Core text-unit processing
# ---------------------------------------------------------------------------

def tokenize_text(text: str, pseudonymizer, detector) -> str:
    """Detect PII in a single text string and return tokenized version."""
    detections = detector.detect(text)
    tokenized, _ = pseudonymizer.pseudonymize(text, detections)
    return tokenized


# ---------------------------------------------------------------------------
# Format-specific processors
# ---------------------------------------------------------------------------

def process_txt(
    input_path: str,
    output_path: str,
    pseudonymizer,
    detector,
) -> int:
    """Process a plain-text file line by line with progress bar."""
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    chars = 0
    tokenized_lines = []
    for line in tqdm(lines, desc="Tokenizing", unit="line"):
        tokenized_lines.append(tokenize_text(line, pseudonymizer, detector))
        chars += len(line)

    with open(output_path, "w", encoding="utf-8", errors="replace") as f:
        f.writelines(tokenized_lines)

    return chars


def _tokenize_item(item: Any, pseudonymizer, detector) -> Any:
    """Tokenize PII inside a JSON item, preserving its structure."""
    if isinstance(item, str):
        return tokenize_text(item, pseudonymizer, detector)
    if isinstance(item, dict):
        if "text" in item:
            item = dict(item)  # shallow copy to avoid mutating original
            item["text"] = tokenize_text(item["text"], pseudonymizer, detector)
        return item
    return item


def process_json(
    input_path: str,
    output_path: str,
    pseudonymizer,
    detector,
) -> int:
    """
    Process a JSON file. Handles:
    - list of {"text": ...} dicts  (training dataset format)
    - list of strings
    - single {"text": ...} dict
    Returns number of text characters processed.
    """
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    chars = 0

    if isinstance(data, list):
        output = []
        for item in tqdm(data, desc="Tokenizing", unit="sample"):
            original_text = item["text"] if isinstance(item, dict) and "text" in item else (item if isinstance(item, str) else "")
            chars += len(original_text)
            output.append(_tokenize_item(item, pseudonymizer, detector))
    elif isinstance(data, dict) and "text" in data:
        chars += len(data["text"])
        output = _tokenize_item(data, pseudonymizer, detector)
    else:
        # Fallback: serialize to string, tokenize, parse back
        raw = json.dumps(data, ensure_ascii=False)
        chars += len(raw)
        tokenized_raw = tokenize_text(raw, pseudonymizer, detector)
        try:
            output = json.loads(tokenized_raw)
        except json.JSONDecodeError:
            output = tokenized_raw  # store as string if JSON broke

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return chars


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def process_file(
    input_path: str,
    output_path: str,
    aes_key: bytes = DEFAULT_AES_KEY.encode("utf-8"),
    model_path: str = DEFAULT_MODEL_PATH,
    use_ai: bool = True,
    ai_threshold: float = 0.95,
    redis_url: str | None = None,
    redis_ttl: int = rc.DEFAULT_TTL,
    session_id: str | None = None,
) -> dict:
    """
    Tokenize PII in any supported file type and write:
      - <output_path>  : file with PII replaced by tokens
      - Redis          : tokenmap:{session_id}, filemap:{filename}, keyref:{session_id}

    Pass an existing session_id to merge tokens into that session.
    Returns a dict with session_id, key_id, and map_location for the caller.
    Rolls back the output file if the Redis write fails.
    """
    redis_url  = redis_url  or rc.DEFAULT_REDIS_URL
    session_id = session_id or str(uuid.uuid4())

    print("Loading dependencies...")
    from hybrid_detect import HybridDetector
    from pseudonymize import PIIPseudonymizer
    print("Ready.")

    print(f"\nInitializing detector (AI={'enabled' if use_ai else 'disabled'})...")
    detector = HybridDetector(model_path, use_ai=use_ai, ai_threshold=ai_threshold)
    pseudonymizer = PIIPseudonymizer(aes_key)

    ext = os.path.splitext(input_path)[1].lower()

    print(f"\nProcessing: {input_path}")
    if ext == ".json":
        chars = process_json(input_path, output_path, pseudonymizer, detector)
    else:
        chars = process_txt(input_path, output_path, pseudonymizer, detector)

    token_map = pseudonymizer.get_token_map()
    filename   = os.path.basename(input_path)
    key_id     = hashlib.sha256(aes_key).hexdigest()[:12]

    try:
        rc.store_token_map(
            token_map=token_map,
            session_id=session_id,
            filename=filename,
            key_id=key_id,
            url=redis_url,
            ttl=redis_ttl,
        )
        map_location = f"redis tokenmap:{session_id} @ {redis_url}"  # noqa
    except Exception as exc:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(
            f"Redis write failed — output file removed to prevent data loss: {exc}"
        ) from exc

    print(f"\n{'='*60}")
    print(f"  Characters processed : {chars:,}")
    print(f"  Unique PII values    : {len(token_map)}")
    print(f"  Tokenized output     : {output_path}")
    print(f"  Token map            : {map_location}")
    print(f"  Session ID           : {session_id}")
    print(f"  Key ID               : {key_id}")
    print(f"{'='*60}\n")

    return {"session_id": session_id, "key_id": key_id, "map_location": map_location}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_output(input_path: str) -> str:
    stem, ext = os.path.splitext(input_path)
    return f"{stem}_tokenized{ext}"


def main() -> None:
    print("PII Tokenizer — loading arguments...")

    parser = argparse.ArgumentParser(
        description="Replace PII in any text file with readable tokens and save a recovery map."
    )
    parser.add_argument("--input", required=True, help="Path to input file (.txt, .json, ...)")
    parser.add_argument("--output", default=None, help="Output file path (default: <stem>_tokenized.<ext>)")
    parser.add_argument("--key", default=DEFAULT_AES_KEY, help=f"AES key string — must be 16, 24, or 32 bytes (default: '{DEFAULT_AES_KEY}')")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, dest="model_path", help=f"Path to AI model directory (default: '{DEFAULT_MODEL_PATH}')")
    parser.add_argument("--no-ai", action="store_true", dest="no_ai", help="Presidio-only mode (faster, no model load)")
    parser.add_argument("--ai-threshold", type=float, default=0.95, dest="ai_threshold", help="Min confidence for AI detections (default: 0.95)")
    parser.add_argument("--redis", default=rc.DEFAULT_REDIS_URL, dest="redis_url", metavar="REDIS_URL", help=f"Redis URL (default: $REDIS_URL or redis://localhost:6379)")
    parser.add_argument("--redis-ttl", type=int, default=rc.DEFAULT_TTL, dest="redis_ttl", metavar="SECONDS", help=f"TTL in seconds for Redis keys (default: {rc.DEFAULT_TTL} = 30 days)")
    args = parser.parse_args()

    aes_key = args.key.encode("utf-8")
    if len(aes_key) not in (16, 24, 32):
        print(f"ERROR: AES key must be 16, 24, or 32 bytes; got {len(aes_key)}")
        sys.exit(1)

    if not (0.0 <= args.ai_threshold <= 1.0):
        print(f"ERROR: --ai-threshold must be between 0.0 and 1.0; got {args.ai_threshold}")
        sys.exit(1)

    output_path = args.output or _default_output(args.input)

    process_file(
        input_path=args.input,
        output_path=output_path,
        aes_key=aes_key,
        model_path=args.model_path,
        use_ai=not args.no_ai,
        ai_threshold=args.ai_threshold,
        redis_url=args.redis_url,
        redis_ttl=args.redis_ttl,
    )


if __name__ == "__main__":
    main()
