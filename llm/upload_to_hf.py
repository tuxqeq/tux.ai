"""
upload_to_hf.py — Upload tux.ai project and/or model to Hugging Face Hub.

Two upload modes (both can run together):

  --code   Push full project source to a HF dataset repo (downloadable on RunPod)
  --model  Upload GGUF + Modelfile to a HF model repo

Usage:
    pip install huggingface_hub
    huggingface-cli login              # paste a write token from hf.co/settings/tokens

    # Upload everything (code + model):
    python llm/upload_to_hf.py --code --model

    # Code only (no GGUF required):
    python llm/upload_to_hf.py --code

    # Model only:
    python llm/upload_to_hf.py --model

On RunPod after code upload:
    git clone https://huggingface.co/datasets/tuxqeq/tux.ai
"""

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXPORT_DIR = os.path.join(_REPO_ROOT, "llm", "export")

DEFAULT_CODE_REPO  = "tuxqeq/tux.ai"        # HF dataset repo for full project
DEFAULT_MODEL_REPO = "tuxqeq/tux-ai-chat"   # HF model repo for GGUF

# Files/dirs to exclude when uploading project code
IGNORE_PATTERNS = [
    # Python / tooling
    ".venv/**", "venv/**",
    "**/__pycache__/**", "*.pyc", "*.pyo",
    ".git/**",
    ".DS_Store",
    "*.log", "logs/**",
    ".cache/**",
    ".env", ".env.local",
    # Large binary formats that are not model weights
    "*.onnx", "*.ckpt",
    # LLM training artifacts
    "llm/export/**", "llm/exports/**",
    "llm/checkpoints/**",
    "llm/data/**",
    "*.gguf",
    # Training / raw data (large, not needed to run the pipeline)
    "data/**",
    "input/large_data.txt",
    "output/**",
    # Redis
    "dump.rdb",
    # Internal / ephemeral
    "CLAUDE.md",
    "todo.md",
    "tmp/**", "temp/**",
    "*.tmp", "*.temp",
    # Jupyter checkpoints
    ".ipynb_checkpoints/**",
    "wandb/**",
]

MODEL_CARD = """\
---
language:
- en
license: apache-2.0
base_model: Qwen/Qwen3-8B
tags:
- qwen3
- qlora
- pii
- privacy
- tokenization
- gguf
- ollama
---

# tux-ai-chat

A Qwen3-8B chatbot fine-tuned on tokenized PII records via QLoRA.

## What it does

All personally identifiable information is replaced with `[TYPE_hash]` placeholders
(e.g. `[PERSON_a1b2c3d4]`, `[SSN_e5f6g7h8]`). The model can:

- Generate synthetic tokenized records
- Answer questions about specific fields in a tokenized record
- Summarize tokenized records while preserving all placeholders
- Extract and reformat sections of tokenized records
- Hold multi-turn conversations about records

It **never** emits raw PII and **never** attempts to decode placeholders.

## Quickstart (Ollama)

```bash
ollama create tux-ai-chat -f Modelfile
ollama run tux-ai-chat
```

Example prompts:
```
Generate a customer record for a healthcare professional.
```
```
What is the SSN token in this record?
[paste tokenized record]
```

## Training details

| Setting | Value |
|---|---|
| Base model | `Qwen/Qwen3-8B` |
| Method | QLoRA (4-bit, r=16, alpha=32) |
| Training data | 1 000 synthetic tokenized records, ~6 000 chat examples |
| Epochs | 3 |
| Thinking mode | Disabled (`enable_thinking=False`) |
| Quantization | Q8_0 GGUF |

## Full project

[github.com/tuxqeq/tux.ai](https://github.com/tuxqeq/tux.ai)
"""

CODE_REPO_CARD = """\
---
license: apache-2.0
tags:
- pii
- privacy
- presidio
- bert
- qwen3
- tokenization
language:
- en
---

# tux.ai — Hybrid PII Detection & LLM Training Pipeline

Full project source for the tux.ai PII detection, tokenization, and LLM fine-tuning system.

## What's included

- `src/` — Hybrid PII detector (Presidio + fine-tuned DistilBERT), pseudonymizer, Redis token store
- `llm/` — Qwen3-8B QLoRA fine-tuning pipeline on tokenized records
- `requirements.txt` / `requirements-llm.txt` — dependencies

## Quick start on RunPod

```bash
git clone https://huggingface.co/datasets/tuxqeq/tux.ai
cd tux.ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-llm.txt

redis-server --dir /tmp &
python llm/generate_synthetic_docs.py --count 1000
python llm/prepare_corpus.py --no-ai
python llm/build_chat_dataset.py
python llm/train_qlora.py --train-file llm/data/chat/train.jsonl --val-file llm/data/chat/val.jsonl
python llm/export_to_gguf.py --merged-model-dir llm/checkpoints/run_001/merged_16bit/
```

## GitHub

[github.com/tuxqeq/tux.ai](https://github.com/tuxqeq/tux.ai)
"""


def _check_login(api):
    try:
        whoami = api.whoami()
        print(f"Logged in as: {whoami['name']}")
        return whoami["name"]
    except Exception:
        print("Not logged in. Run: huggingface-cli login")
        sys.exit(1)


def upload_code(api, repo_id: str, private: bool) -> None:
    from huggingface_hub import create_repo

    print(f"\n{'='*60}")
    print(f"  Uploading project code → {repo_id}")
    print(f"{'='*60}")

    create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    print(f"  Repo: https://huggingface.co/datasets/{repo_id}")

    # Upload README/dataset card
    print("  Uploading dataset card...")
    api.upload_file(
        path_or_fileobj=CODE_REPO_CARD.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Add dataset card",
    )

    # Upload full project folder
    print(f"  Uploading project files from {_REPO_ROOT} ...")
    print(f"  (excluding: {', '.join(IGNORE_PATTERNS[:6])} ...)")
    api.upload_folder(
        folder_path=_REPO_ROOT,
        repo_id=repo_id,
        repo_type="dataset",
        ignore_patterns=IGNORE_PATTERNS,
        commit_message="Upload tux.ai project source",
    )
    print("\n  Code upload complete!")
    print("  Clone on RunPod with:")
    print(f"    git clone https://huggingface.co/datasets/{repo_id}")


def upload_model(api, repo_id: str, export_dir: str, private: bool) -> None:
    from huggingface_hub import create_repo

    print(f"\n{'='*60}")
    print(f"  Uploading model → {repo_id}")
    print(f"{'='*60}")

    create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
    print(f"  Repo: https://huggingface.co/{repo_id}")

    print("  Uploading model card...")
    api.upload_file(
        path_or_fileobj=MODEL_CARD.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
        commit_message="Add model card",
    )

    # Find and upload GGUF
    gguf_path = next(
        (os.path.join(export_dir, f) for f in os.listdir(export_dir) if f.endswith(".gguf")),
        None,
    )
    if not gguf_path:
        print(f"  WARNING: No .gguf file found in {export_dir} — skipping GGUF upload.")
    else:
        size_gb = os.path.getsize(gguf_path) / 1e9
        print(f"  Uploading {os.path.basename(gguf_path)} ({size_gb:.1f} GB) — this takes a while...")
        api.upload_file(
            path_or_fileobj=gguf_path,
            path_in_repo=os.path.basename(gguf_path),
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Add {os.path.basename(gguf_path)}",
        )

    # Find and upload Modelfile
    modelfile_path = next(
        (os.path.join(export_dir, f) for f in os.listdir(export_dir)
         if "modelfile" in f.lower() or f == "Modelfile"),
        None,
    )
    if modelfile_path:
        print("  Uploading Modelfile...")
        api.upload_file(
            path_or_fileobj=modelfile_path,
            path_in_repo="Modelfile",
            repo_id=repo_id,
            repo_type="model",
            commit_message="Add Modelfile for Ollama",
        )

    print("\n  Model upload complete!")
    print(f"  https://huggingface.co/{repo_id}")


def _is_ignored(rel_path: str) -> bool:
    import fnmatch
    normalized = rel_path.replace("\\", "/")
    basename = os.path.basename(normalized)
    return any(
        fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(basename, pat)
        for pat in IGNORE_PATTERNS
    )


def _collect_code_files() -> list[tuple[str, int]]:
    """Return (relative_path, size_bytes) for every non-ignored file under _REPO_ROOT."""
    result = []
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = [
            d for d in dirs
            if not _is_ignored(os.path.relpath(os.path.join(root, d), _REPO_ROOT))
        ]
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, _REPO_ROOT)
            if not _is_ignored(rel):
                result.append((rel, os.path.getsize(fpath)))
    return result


def _dry_run(args) -> None:
    """Print what would be uploaded without touching HuggingFace."""
    if args.code:
        print(f"\nDRY RUN — files that would be uploaded to {args.code_repo}:")
        files = _collect_code_files()
        for rel, size in files:
            print(f"  {rel}  ({size/1024:.0f} KB)")
        print(f"\n  Total: {sum(s for _, s in files)/1e6:.1f} MB")

    if args.model:
        print(f"\nDRY RUN — files that would be uploaded to {args.model_repo}:")
        if os.path.isdir(args.export_dir):
            for fname in os.listdir(args.export_dir):
                size = os.path.getsize(os.path.join(args.export_dir, fname))
                print(f"  {fname}  ({size/1e9:.2f} GB)")
        else:
            print(f"  Export dir not found: {args.export_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload tux.ai project and/or model to Hugging Face Hub."
    )
    parser.add_argument("--code",  action="store_true",
                        help="Upload full project source to a dataset repo")
    parser.add_argument("--model", action="store_true",
                        help="Upload GGUF model to a model repo")
    parser.add_argument("--code-repo",  default=DEFAULT_CODE_REPO,
                        help=f"HF dataset repo id (default: {DEFAULT_CODE_REPO})")
    parser.add_argument("--model-repo", default=DEFAULT_MODEL_REPO,
                        help=f"HF model repo id (default: {DEFAULT_MODEL_REPO})")
    parser.add_argument("--export-dir", default=DEFAULT_EXPORT_DIR,
                        help=f"Directory with GGUF + Modelfile (default: {DEFAULT_EXPORT_DIR})")
    parser.add_argument("--private", action="store_true",
                        help="Create repos as private")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be uploaded without actually uploading")
    args = parser.parse_args()

    if not args.code and not args.model:
        parser.error("Specify at least one of --code or --model (or both).")

    if args.dry_run:
        _dry_run(args)
        return

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    api = HfApi()
    _check_login(api)

    if args.code:
        upload_code(api, args.code_repo, args.private)

    if args.model:
        if not os.path.isdir(args.export_dir):
            print(f"Export dir not found: {args.export_dir}")
            sys.exit(1)
        upload_model(api, args.model_repo, args.export_dir, args.private)

    print(f"\n{'='*60}")
    if args.code:
        print(f"  Code : https://huggingface.co/datasets/{args.code_repo}")
    if args.model:
        print(f"  Model: https://huggingface.co/{args.model_repo}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
