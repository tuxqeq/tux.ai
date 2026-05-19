"""
setup_chat.py — One-shot setup after cloning tux.ai from HuggingFace.

Downloads the GGUF model, writes a ready-to-use Modelfile, and verifies
the PII detector models are present so both the chatbot and the training
pipeline work immediately.

Usage (after git clone):
    pip install -r requirements.txt -r requirements-llm.txt
    python setup_chat.py
    ollama run tux-ai-chat
"""

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_EXPORT_DIR = os.path.join(_REPO_ROOT, "llm", "export")
_MODELS_DIR = os.path.join(_REPO_ROOT, "models")

HF_MODEL_REPO  = "tuxqeq/tux-ai-chat"       # GGUF lives here
HF_CODE_REPO   = "datasets/tuxqeq/tux.ai"   # informational
GGUF_FILENAME  = "Model Q8 0.gguf"
MODELFILE_NAME = "Modelfile"
OLLAMA_NAME    = "tux-ai-chat"

MODELFILE_CONTENT = """\
FROM {gguf_path}

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.05
PARAMETER num_ctx 4096

SYSTEM \"\"\"You are a document assistant trained on tokenized records. \
Personally identifiable information appears as placeholder tokens in the \
format [TYPE_hash] (for example [PERSON_a1b2c3d4], [SSN_e5f6g7h8]). \
Always preserve this exact format in your responses. \
Never invent untokenized PII. Never attempt to decode placeholders.\"\"\"
"""


def _check_huggingface_hub():
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
        return hf_hub_download, snapshot_download
    except ImportError:
        print("huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)


def _download_gguf(hf_hub_download, force: bool) -> str:
    gguf_path = os.path.join(_EXPORT_DIR, GGUF_FILENAME)

    if os.path.exists(gguf_path) and not force:
        size_gb = os.path.getsize(gguf_path) / 1e9
        print(f"  GGUF already present ({size_gb:.1f} GB): {gguf_path}")
        return gguf_path

    os.makedirs(_EXPORT_DIR, exist_ok=True)
    print(f"  Downloading {GGUF_FILENAME} from {HF_MODEL_REPO} (~8 GB, please wait)...")
    downloaded = hf_hub_download(
        repo_id=HF_MODEL_REPO,
        filename=GGUF_FILENAME,
        local_dir=_EXPORT_DIR,
    )
    # hf_hub_download may return a cache symlink — resolve to actual path
    resolved = os.path.realpath(downloaded)
    final_path = gguf_path
    if resolved != final_path:
        import shutil
        shutil.copy2(resolved, final_path)
    print(f"  Downloaded: {final_path}")
    return final_path


def _write_modelfile(gguf_path: str) -> str:
    modelfile_path = os.path.join(_EXPORT_DIR, MODELFILE_NAME)
    content = MODELFILE_CONTENT.format(gguf_path=os.path.abspath(gguf_path))
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Modelfile written: {modelfile_path}")
    return modelfile_path


def _register_ollama(modelfile_path: str, force: bool) -> None:
    import shutil
    import subprocess

    if not shutil.which("ollama"):
        print("  ollama not found — install from https://ollama.com then run:")
        print(f"    ollama create {OLLAMA_NAME} -f {modelfile_path}")
        return

    # Check if already created
    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True
    )
    already_exists = OLLAMA_NAME in result.stdout

    if already_exists and not force:
        print(f"  Ollama model '{OLLAMA_NAME}' already exists. Use --force to recreate.")
        return

    print(f"  Creating Ollama model '{OLLAMA_NAME}'...")
    result = subprocess.run(
        ["ollama", "create", OLLAMA_NAME, "-f", modelfile_path],
        capture_output=False,
    )
    if result.returncode == 0:
        print(f"  Ollama model ready: {OLLAMA_NAME}")
    else:
        print(f"  ollama create failed. Run manually:")
        print(f"    ollama create {OLLAMA_NAME} -f {modelfile_path}")


def _check_pii_models() -> None:
    print("\n[2/3] PII detector models")
    if not os.path.isdir(_MODELS_DIR) or not os.listdir(_MODELS_DIR):
        print("  WARNING: models/ directory is empty or missing.")
        print("  The PII tokenization pipeline (prepare_corpus.py) will run in")
        print("  Presidio-only mode (--no-ai). To use the AI model, train it first:")
        print("    python src/train.py --smoke_test")
        return

    models = [d for d in os.listdir(_MODELS_DIR)
              if os.path.isdir(os.path.join(_MODELS_DIR, d))]
    print(f"  Found {len(models)} model(s): {', '.join(models)}")
    print("  PII detector ready — full hybrid detection available.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download tux-ai-chat GGUF and set up Ollama after cloning from HuggingFace."
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-download GGUF and recreate Ollama model even if already present")
    parser.add_argument("--skip-ollama", action="store_true",
                        help="Download GGUF but skip Ollama model creation")
    args = parser.parse_args()

    print("tux.ai setup")
    print("=" * 50)

    # Step 1: Download GGUF
    print("\n[1/3] Chatbot model (GGUF)")
    hf_hub_download, _ = _check_huggingface_hub()
    gguf_path = _download_gguf(hf_hub_download, args.force)
    modelfile_path = _write_modelfile(gguf_path)

    if not args.skip_ollama:
        _register_ollama(modelfile_path, args.force)

    # Step 2: Check PII models
    _check_pii_models()

    # Step 3: Summary
    print("\n[3/3] Ready")
    print("=" * 50)
    print(f"  Start chatbot  : ollama run {OLLAMA_NAME}")
    print(f"  Detect PII     : python src/hybrid_detect.py --text 'John at john@email.com' --no-ai")
    print(f"  Full pipeline  : see llm/README.md")
    print("=" * 50)


if __name__ == "__main__":
    main()
