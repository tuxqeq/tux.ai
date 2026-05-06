"""
prepare_corpus.py — Tokenize raw synthetic documents using the tux.ai PII pipeline.

Steps:
  1. Iterates over .txt files in --input-dir
  2. Detects PII via HybridDetector + pseudonymizes with PIIPseudonymizer
  3. Writes tokenized docs to --output-dir
  4. Securely deletes --input-dir (overwrite bytes + unlink + rmtree)

Redis is pinged at startup; the script exits if Redis is unreachable.
"""

import argparse
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
DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "llm", "data", "tokenized")
DEFAULT_AES_KEY = "16ByteSecureKey!"
DEFAULT_MODEL_PATH = os.path.join(_REPO_ROOT, "models", "pii_model_v2")


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
    for root, dirs, files in os.walk(directory):
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
    parser.add_argument("--key", default=DEFAULT_AES_KEY,
                        help="AES key string — must be 16, 24, or 32 bytes")
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
    args = parser.parse_args()

    if args.keep_raw:
        warnings.warn(
            "--keep-raw is set: raw synthetic documents will NOT be deleted. "
            "This flag is for debugging only and must never be used in production.",
            stacklevel=1,
        )

    aes_key = args.key.encode("utf-8")
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

            token_count = len(pseudonymizer.get_token_map())
            print(f"  [OK] {fname}  ({token_count} PII tokens replaced)")
            processed += 1

        except Exception as exc:
            print(f"  [ERR] {fname}: {exc}")
            failed += 1

    print(f"\nResults: {processed} succeeded, {failed} failed")

    # --- Secure deletion ---
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
