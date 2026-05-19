"""
upload_to_hf.py — Upload tux-ai-chat model to Hugging Face Hub.

Uploads:
  - GGUF model file (q8_0)
  - Modelfile for Ollama
  - Auto-generated model card (README.md)

Usage:
    pip install huggingface_hub
    huggingface-cli login          # paste your HF write token
    python llm/upload_to_hf.py
"""

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXPORT_DIR = os.path.join(_REPO_ROOT, "llm", "export")
DEFAULT_HF_REPO = "tuxqeq/tux-ai-chat"

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

The model is trained exclusively on **tokenized text** — all personally
identifiable information is replaced with `[TYPE_hash]` placeholders
(e.g. `[PERSON_a1b2c3d4]`, `[SSN_e5f6g7h8]`). It can:

- Generate synthetic tokenized records
- Answer questions about fields in a tokenized record
- Summarize tokenized records while preserving all placeholders
- Extract and reformat sections of tokenized records
- Hold multi-turn conversations about records

It **never** emits raw PII and **never** attempts to decode placeholders.

## Quickstart (Ollama)

```bash
ollama pull tuxqeq/tux-ai-chat   # if published to Ollama registry
# or with local GGUF:
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
```
Summarize this in two sentences.
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

## System prompt

> You are a document assistant trained on tokenized records. Personally
> identifiable information appears as placeholder tokens in the format
> `[TYPE_hash]`. Always preserve this exact format in your responses.
> Never invent untokenized PII. Never attempt to decode placeholders.

## Repository

[github.com/tuxqeq/tux.ai](https://github.com/tuxqeq/tux.ai)
"""


def _find_gguf(directory: str) -> str | None:
    for fname in os.listdir(directory):
        if fname.endswith(".gguf"):
            return os.path.join(directory, fname)
    return None


def _find_modelfile(directory: str) -> str | None:
    for fname in os.listdir(directory):
        if "modelfile" in fname.lower() or fname == "Modelfile":
            return os.path.join(directory, fname)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload tux-ai-chat model to Hugging Face Hub."
    )
    parser.add_argument("--export-dir", default=DEFAULT_EXPORT_DIR,
                        help=f"Directory containing GGUF and Modelfile (default: {DEFAULT_EXPORT_DIR})")
    parser.add_argument("--repo", default=DEFAULT_HF_REPO,
                        help=f"HF repo id — user/repo-name (default: {DEFAULT_HF_REPO})")
    parser.add_argument("--private", action="store_true",
                        help="Create as private repository")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, create_repo, upload_file
    except ImportError:
        print("huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    api = HfApi()

    # Verify logged in
    try:
        whoami = api.whoami()
        print(f"Logged in as: {whoami['name']}")
    except Exception:
        print("Not logged in. Run: huggingface-cli login")
        sys.exit(1)

    # Create repo
    print(f"\nCreating repository: {args.repo}")
    try:
        create_repo(
            repo_id=args.repo,
            repo_type="model",
            private=args.private,
            exist_ok=True,
        )
        print(f"  https://huggingface.co/{args.repo}")
    except Exception as exc:
        print(f"Failed to create repo: {exc}")
        sys.exit(1)

    # Upload model card
    print("\nUploading model card (README.md)...")
    api.upload_file(
        path_or_fileobj=MODEL_CARD.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.repo,
        repo_type="model",
        commit_message="Add model card",
    )

    # Upload GGUF
    gguf_path = _find_gguf(args.export_dir)
    if not gguf_path:
        print(f"No .gguf file found in {args.export_dir}")
        sys.exit(1)

    gguf_name = os.path.basename(gguf_path)
    size_gb = os.path.getsize(gguf_path) / 1e9
    print(f"\nUploading GGUF: {gguf_name} ({size_gb:.1f} GB) — this will take a while...")
    api.upload_file(
        path_or_fileobj=gguf_path,
        path_in_repo=gguf_name,
        repo_id=args.repo,
        repo_type="model",
        commit_message=f"Add {gguf_name}",
    )
    print("  Done.")

    # Upload Modelfile
    modelfile_path = _find_modelfile(args.export_dir)
    if modelfile_path:
        print("\nUploading Modelfile...")
        api.upload_file(
            path_or_fileobj=modelfile_path,
            path_in_repo="Modelfile",
            repo_id=args.repo,
            repo_type="model",
            commit_message="Add Modelfile for Ollama",
        )
        print("  Done.")

    print(f"\n{'='*60}")
    print(f"  Upload complete!")
    print(f"  Model page : https://huggingface.co/{args.repo}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
