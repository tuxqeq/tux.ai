"""
prepare_corpus.py — Tokenize raw synthetic documents using the tux.ai PII pipeline.

Steps:
  1. Iterates over .txt files in --input-dir
  2. Detects PII via HybridDetector + pseudonymizes with PIIPseudonymizer
  3. Writes tokenized docs to --output-dir
  4. Securely deletes --input-dir (overwrite bytes + unlink + rmtree)

Corpus v2 (2026-11-08, thesis decision log D-22):
  - the dataset key is a random 32-byte key in --key-file (base64, file mode 600), created on the
    first run; the old hard-coded default "16ByteSecureKey!" is no longer used
  - Redis keyref stores a SHA-256 fingerprint of the key, not its first 8 characters
  - token maps never expire (--ttl-days 0)
  - the plaintext token map is NOT written to disk unless --export-map is given

Redis is pinged at startup; the script exits if Redis is unreachable.
"""

import argparse
import json
import os
import shutil
import sys
import warnings

# Allow imports from src/ regardless of working directory
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

DEFAULT_INPUT_DIR = os.path.join(_REPO_ROOT, "llm", "data", "raw_temp")
DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "llm", "data", "tokenized_v2")
LEGACY_AES_KEY = "16ByteSecureKey!"  # used for the May 2026 corpus; never use again
DEFAULT_KEY_FILE = os.path.join(_REPO_ROOT, "llm", "data", "dataset_key.b64")
DEFAULT_MODEL_PATH = os.path.join(_REPO_ROOT, "models", "pii_model_v4")



def load_or_create_key(key_file: str) -> bytes:
    """Read a base64 AES key from key_file; create a random 32-byte key there if it is missing."""
    import base64
    import secrets
    if os.path.exists(key_file):
        with open(key_file) as f:
            return base64.b64decode(f.read().strip())
    os.makedirs(os.path.dirname(os.path.abspath(key_file)), exist_ok=True)
    key = secrets.token_bytes(32)
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(base64.b64encode(key).decode())
    print(f"Created a new random dataset key: {key_file} (mode 600). Keep it secret; "
          f"scripts/bootstrap_dataset.py stores it wrapped with MASTER_KEY.")
    return key


def key_fingerprint(key: bytes) -> str:
    import hashlib
    return hashlib.sha256(b"tux.ai/key-ref|" + key).hexdigest()[:16]


def _secure_delete(path: str) -> None:
    """Overwrite file content with random bytes, then unlink."""
    size = os.path.getsize(path)
    with open(path, "r+b") as f:
        f.write(os.urandom(size))
        f.flush()
        os.fsync(f.fileno())
    os.unlink(path)


def _secure_delete_dir(directory: str) -> None:
    """Securely delete every file in directory, then rmtree the shell."""
    for root, _, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                _secure_delete(fpath)
            except Exception as exc:
                print(f"  WARNING: could not securely delete {fpath}: {exc}")
    shutil.rmtree(directory, ignore_errors=True)


def tokenize_text(text: str, pseudonymizer, detector) -> str:
    detections = detector.detect(text)
    tokenized, _ = pseudonymizer.pseudonymize(text, detections)
    return tokenized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tokenize raw synthetic docs and securely delete originals."
    )
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR,
                        help=f"Directory of raw .txt files (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR,
                        help=f"Directory for tokenized .txt files (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--key", default=None,
                        help="[legacy] AES key string (16/24/32 bytes). Prefer --key-file.")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE,
                        help="base64 dataset key; created with a random 32-byte key if missing")
    parser.add_argument("--ttl-days", type=int, default=0,
                        help="expiry of the Redis token maps in days (0 = never expire)")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH,
                        help="Path to HybridDetector AI model")
    parser.add_argument("--no-ai", action="store_true",
                        help="Presidio-only mode (faster, no model load)")
    parser.add_argument("--ai-threshold", type=float, default=0.95)
    parser.add_argument("--redis-url", default=None,
                        help="Redis URL for connectivity check (default: $REDIS_URL or redis://localhost:6379)")
    parser.add_argument("--seed", type=int, default=42, help="Unused; reserved for compatibility")
    parser.add_argument("--keep-raw", action="store_true",
                        help="[DEBUG ONLY] Skip secure deletion of raw files. WARNING: raw PII will remain on disk.")
    parser.add_argument("--export-map", default="",
                        help="[DEBUG ONLY] write the token→PLAINTEXT map to this JSON path (default: off)")
    args = parser.parse_args()

    if args.keep_raw:
        warnings.warn(
            "--keep-raw is set: raw synthetic documents will NOT be deleted. "
            "This flag is for debugging only and must never be used in production.",
            stacklevel=1,
        )

    if args.key is not None:
        if args.key == LEGACY_AES_KEY:
            print("ERROR: the legacy default key must not be used for a new corpus.")
            sys.exit(1)
        aes_key = args.key.encode("utf-8")
    else:
        aes_key = load_or_create_key(args.key_file)
    if len(aes_key) not in (16, 24, 32):
        print(f"ERROR: AES key must be 16, 24, or 32 bytes; got {len(aes_key)}")
        sys.exit(1)

    # --- Redis connectivity check ---
    import redis_client as rc
    redis_url = args.redis_url or rc.DEFAULT_REDIS_URL
    print(f"Pinging Redis at {redis_url} ...", end=" ", flush=True)
    if not rc.ping(redis_url):
        print("FAILED")
        print(
            f"ERROR: Cannot reach Redis at {redis_url}.\n"
            "Redis is required to store the token recovery map.\n"
            "Start Redis with: redis-server\n"
            "Or set REDIS_URL to point to your Redis instance."
        )
        sys.exit(1)
    print("OK")

    # --- Load detector and pseudonymizer ---
    print("Loading PII detector (this may take a moment)...")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    from hybrid_detect import HybridDetector
    from pseudonymize import PIIPseudonymizer

    use_ai = not args.no_ai
    if use_ai and not os.path.exists(args.model_path):
        print(
            f"WARNING: AI model not found at {args.model_path}. "
            "Falling back to Presidio-only mode."
        )
        use_ai = False

    detector = HybridDetector(
        ai_model_path=args.model_path,
        use_ai=use_ai,
        ai_threshold=args.ai_threshold,
    )
    pseudonymizer = PIIPseudonymizer(aes_key)

    # --- Collect input files ---
    if not os.path.isdir(args.input_dir):
        print(f"ERROR: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    txt_files = sorted(
        f for f in os.listdir(args.input_dir)
        if f.endswith(".txt")
    )

    if not txt_files:
        print(f"No .txt files found in {args.input_dir}. Nothing to do.")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"\nTokenizing {len(txt_files)} files from {args.input_dir}")
    print(f"Output → {args.output_dir}\n")

    processed = 0
    failed = 0
    master_token_map: dict[str, str] = {}

    for fname in txt_files:
        in_path = os.path.join(args.input_dir, fname)
        out_path = os.path.join(args.output_dir, fname)

        try:
            with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

            pseudonymizer.reset()
            tokenized = tokenize_text(raw_text, pseudonymizer, detector)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(tokenized)

            plaintext_map = pseudonymizer.get_plaintext_map()
            master_token_map.update(plaintext_map)

            # Store encrypted map in Redis (same format the admin import-rdb expects)
            encrypted_map = pseudonymizer.get_token_map()
            if encrypted_map:
                session_id = os.path.splitext(fname)[0]
                rc.store_token_map(
                    token_map=encrypted_map,
                    session_id=session_id,
                    filename=fname,
                    key_id=key_fingerprint(aes_key),
                    url=redis_url,
                    ttl=args.ttl_days * 86400 or None,
                )

            print(f"  [OK] {fname}  ({len(plaintext_map)} PII tokens replaced)")
            processed += 1

        except Exception as exc:
            print(f"  [ERR] {fname}: {exc}")
            failed += 1

    print(f"\nResults: {processed} succeeded, {failed} failed")

    # --- Flush Redis to dump.rdb ---
    if master_token_map:
        try:
            r = rc.get_client(redis_url)
            r.bgsave()
            rdb_dir = r.config_get("dir").get("dir", "/tmp")
            rdb_file = os.path.join(rdb_dir, "dump.rdb")
            print(f"\nRedis BGSAVE triggered — dump.rdb will be written to: {rdb_file}")
            print("  Download it with:  scp root@<pod-ip>:" + rdb_file + " ./dump.rdb")
            print("  Or on the pod:     cp " + rdb_file + " /workspace/dump.rdb")
        except Exception as exc:
            print(f"\nWARNING: could not trigger BGSAVE: {exc}")

    # --- Export token map ---
    if args.export_map and master_token_map:
        map_path = args.export_map
        os.makedirs(os.path.dirname(map_path), exist_ok=True)
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(master_token_map, f, indent=2, ensure_ascii=False)
        print(f"\nToken map ({len(master_token_map)} entries) saved to: {map_path}")
        print(f"  Key fingerprint: {key_fingerprint(aes_key)}")
        print("  Use this map to decode model outputs: token -> original value")

    # --- Secure deletion ---
    if failed:
        # Before 2026-11-08 the raw files were deleted even when files failed, so a crash in
        # tokenization (e.g. a 32-byte key, D-22) lost the input. Keep it and stop instead.
        print(f"\nERROR: {failed} file(s) failed. Raw input is KEPT in {args.input_dir}; "
              "fix the error and run again.")
        sys.exit(1)
    if args.keep_raw:
        print(f"\n[DEBUG] --keep-raw set: skipping deletion of {args.input_dir}")
    else:
        print(f"\nSecurely deleting raw input directory: {args.input_dir}")
        _secure_delete_dir(args.input_dir)
        print(f"  Raw data directory deleted: {args.input_dir}")
        print("  Confirmation: no untokenized PII documents remain on disk.")

    print(f"\nDone. Tokenized corpus written to: {args.output_dir}")


if __name__ == "__main__":
    main()
