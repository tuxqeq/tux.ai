"""
export_to_gguf.py — Convert a merged 16-bit model to GGUF for Ollama.

Two code paths:
  1. Unsloth built-in GGUF export (preferred — model loaded in memory)
  2. llama.cpp convert_hf_to_gguf.py via subprocess (fallback)

After export, writes a concrete Modelfile and prints ollama commands.

Usage:
    python llm/export_to_gguf.py \
        --merged-model-dir llm/checkpoints/run_001/merged_16bit/
"""

import argparse
import os
import shutil
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "llm", "exports")
MODELFILE_TEMPLATE = os.path.join(_REPO_ROOT, "llm", "Modelfile.template")


def _find_gguf(directory: str) -> str | None:
    for fname in os.listdir(directory):
        if fname.endswith(".gguf"):
            return os.path.join(directory, fname)
    return None


def _render_modelfile(template_path: str, gguf_path: str, output_path: str) -> None:
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("{GGUF_PATH}", gguf_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def _find_fast_language_model():
    """Locate FastLanguageModel across unsloth package layouts (2024 vs 2025+)."""
    import importlib
    for mod_name, attr in [
        ("unsloth", "FastLanguageModel"),
        ("unsloth_zoo", "FastLanguageModel"),
        ("unsloth_zoo.training_utils", "FastLanguageModel"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, attr, None)
            if cls is not None and hasattr(cls, "from_pretrained"):
                return cls
        except Exception:
            pass
    return None


def export_via_unsloth(merged_dir: str, output_dir: str, quantization: str) -> str | None:
    """Try Unsloth's built-in GGUF export. Returns GGUF path on success, None on failure."""
    fast_lm_cls = _find_fast_language_model()
    if fast_lm_cls is None:
        print("Unsloth FastLanguageModel not available; skipping Unsloth export path.")
        return None

    print("Loading merged model via Unsloth for GGUF export...")
    try:
        model, tokenizer = fast_lm_cls.from_pretrained(
            model_name=merged_dir,
            max_seq_length=4096,
            dtype=None,
            load_in_4bit=False,
        )
    except Exception as exc:
        print(f"Could not load model via Unsloth: {exc}")
        return None

    print(f"Exporting to GGUF ({quantization}) via Unsloth...")
    os.makedirs(output_dir, exist_ok=True)
    try:
        model.save_pretrained_gguf(
            output_dir,
            tokenizer,
            quantization_method=quantization,
        )
    except Exception as exc:
        print(f"Unsloth GGUF export failed: {exc}")
        return None

    gguf_path = _find_gguf(output_dir)
    if gguf_path:
        print(f"Unsloth GGUF export succeeded: {gguf_path}")
    return gguf_path


def _find_llamacpp_convert() -> str | None:
    """Find convert_hf_to_gguf.py, including Unsloth's bundled llama.cpp."""
    candidate = shutil.which("convert_hf_to_gguf.py")
    if candidate:
        return candidate
    search_paths = [
        # Unsloth builds llama.cpp here
        "/root/.unsloth/llama.cpp/convert_hf_to_gguf.py",
        os.path.expanduser("~/.unsloth/llama.cpp/convert_hf_to_gguf.py"),
        # Manual clones
        os.path.expanduser("~/llama.cpp/convert_hf_to_gguf.py"),
        os.path.expanduser("~/llama.cpp/convert-hf-to-gguf.py"),
        "/usr/local/lib/llama.cpp/convert_hf_to_gguf.py",
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    return None


def export_via_llamacpp(merged_dir: str, output_dir: str, quantization: str) -> str | None:
    """Fallback: use llama.cpp's convert_hf_to_gguf.py."""
    llamacpp_convert = _find_llamacpp_convert()

    if not llamacpp_convert:
        print(
            "ERROR: llama.cpp convert_hf_to_gguf.py not found.\n"
            "Clone llama.cpp and install it:\n"
            "  git clone https://github.com/ggerganov/llama.cpp\n"
            "  cd llama.cpp && pip install -r requirements/requirements-convert_hf_to_gguf.txt\n"
            "Then re-run with: python llm/export_to_gguf.py --merged-model-dir <path>"
        )
        return None

    os.makedirs(output_dir, exist_ok=True)
    gguf_stem = os.path.join(output_dir, "model")

    os.makedirs(output_dir, exist_ok=True)

    # Map quantization to llama.cpp --outtype values.
    # q4_k_m / q5_k_m are not supported by convert_hf_to_gguf directly;
    # use q8_0 as a single-pass output (~8 GB vs 16 GB for f16), then
    # further quantize with llama-quantize if available.
    outtype_map = {
        "q8_0":   "q8_0",
        "q5_k_m": "q8_0",   # intermediate; llama-quantize refines if present
        "q4_k_m": "q8_0",   # intermediate; llama-quantize refines if present
        "f16":    "f16",
    }
    outtype = outtype_map.get(quantization.lower(), "q8_0")
    intermediate_gguf = os.path.join(output_dir, f"model_{outtype}.gguf")

    print(f"Running llama.cpp conversion (outtype={outtype}) from {merged_dir} ...")
    cmd = [
        sys.executable,
        llamacpp_convert,
        merged_dir,
        "--outfile", intermediate_gguf,
        "--outtype", outtype,
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("llama.cpp conversion failed.")
        return None

    if not os.path.exists(intermediate_gguf):
        intermediate_gguf = _find_gguf(output_dir)

    if not intermediate_gguf:
        print("ERROR: GGUF file not found after conversion.")
        return None

    # Try to refine quantization with llama-quantize (optional step)
    if quantization.lower() not in ("f16", "q8_0"):
        llama_quantize = shutil.which("llama-quantize") or shutil.which("quantize")
        if llama_quantize:
            q_map = {"q4_k_m": "Q4_K_M", "q5_k_m": "Q5_K_M"}
            quant_type = q_map.get(quantization.lower(), "Q4_K_M")
            q_gguf = os.path.join(output_dir, f"model_{quant_type}.gguf")
            print(f"Quantizing {outtype} → {quant_type} ...")
            q_result = subprocess.run([llama_quantize, intermediate_gguf, q_gguf, quant_type])
            if q_result.returncode == 0 and os.path.exists(q_gguf):
                os.remove(intermediate_gguf)
                return q_gguf

    return intermediate_gguf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export merged model to GGUF for Ollama."
    )
    parser.add_argument("--merged-model-dir", required=True,
                        help="Path to merged_16bit/ directory from train_qlora.py")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR,
                        help=f"Output directory for GGUF and Modelfile (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--quantization", default="q4_k_m",
                        choices=["q4_k_m", "q5_k_m", "q8_0", "f16"],
                        help="GGUF quantization method (default: q4_k_m)")
    args = parser.parse_args()

    if not os.path.isdir(args.merged_model_dir):
        print(f"ERROR: Merged model directory not found: {args.merged_model_dir}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Try Unsloth first, fall back to llama.cpp ──────────────────────────────
    gguf_path = export_via_unsloth(args.merged_model_dir, args.output_dir, args.quantization)

    if not gguf_path:
        print("\nFalling back to llama.cpp conversion...")
        gguf_path = export_via_llamacpp(args.merged_model_dir, args.output_dir, args.quantization)

    if not gguf_path:
        print("\nERROR: All GGUF export methods failed.")
        print("Manual option: load the model in Python and call model.save_pretrained_gguf()")
        sys.exit(1)

    # ── Generate Modelfile ────────────────────────────────────────────────────
    modelfile_out = os.path.join(args.output_dir, "Modelfile")
    if os.path.exists(MODELFILE_TEMPLATE):
        _render_modelfile(MODELFILE_TEMPLATE, os.path.abspath(gguf_path), modelfile_out)
        print(f"\nModelfile written to: {modelfile_out}")
    else:
        # Write a minimal fallback Modelfile
        with open(modelfile_out, "w") as f:
            f.write(f"FROM {os.path.abspath(gguf_path)}\n\n")
            f.write('PARAMETER stop "<|im_start|>"\n')
            f.write('PARAMETER stop "<|im_end|>"\n')
            f.write("PARAMETER temperature 0.7\n")
            f.write("PARAMETER num_ctx 4096\n")
        print(f"Minimal Modelfile written to: {modelfile_out}")

    # ── Print usage instructions ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  GGUF export complete!")
    print(f"  GGUF file  : {gguf_path}")
    print(f"  Modelfile  : {modelfile_out}")
    print("")
    print("  To create the Ollama model:")
    print(f"    ollama create tux-ai-chat -f {modelfile_out}")
    print("")
    print("  To start chatting:")
    print("    ollama run tux-ai-chat")
    print("")
    print("  Example prompts:")
    print('    "Generate a customer record for a tech startup employee."')
    print('    (paste a tokenized record) "What is the SSN token in this record?"')
    print('    (paste a tokenized record) "Summarize this in two sentences."')
    print("=" * 60)


if __name__ == "__main__":
    main()
