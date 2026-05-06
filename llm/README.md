# tux.ai LLM Fine-Tuning

Fine-tunes **Qwen3-8B** as a chatbot on tokenized PII data using Unsloth + QLoRA, then exports to GGUF for local testing with Ollama.

The model learns to respond to questions about records where all PII has been replaced with `[TYPE_hash]` placeholders (e.g. `[PERSON_a1b2c3d4]`, `[SSN_e5f6g7h8]`). It never sees raw PII.

---

## Prerequisites

- Python 3.11+
- CUDA-capable GPU with ≥16 GB VRAM (24 GB recommended for Qwen3-8B; see hardware fallback below)
- [Ollama](https://ollama.com) installed (`brew install ollama` on macOS)
- Redis running locally (`brew install redis && redis-server`)

## Installation

```bash
pip install -r requirements-llm.txt
```

> **Note:** `transformers>=4.51.0` is required for Qwen3 support. If you hit import errors, upgrade: `pip install --upgrade transformers`.

---

## Pipeline (five commands)

### 1. Generate synthetic documents

```bash
python llm/generate_synthetic_docs.py --count 1000
```

Writes `llm/data/raw_temp/` with 1 000 synthetic records across five types:
Personal Banking Customer, International Business Client, Government Contractor,
Healthcare Professional, Tech Startup Employee. Uses Faker; all values are fake.

### 2. Tokenize and securely delete originals

```bash
python llm/prepare_corpus.py
```

Runs the tux.ai PII pipeline over every raw doc, writes tokenized versions to
`llm/data/tokenized/`, then **overwrites and deletes** `llm/data/raw_temp/`.
Redis must be reachable — the script exits early if it is not.

### 3. Build chat dataset

```bash
python llm/build_chat_dataset.py
```

Converts tokenized docs into multi-turn dialogue examples and writes:
- `llm/data/chat/train.jsonl` (90%)
- `llm/data/chat/val.jsonl`   (10%)

Each document produces ~6 examples across five conversation categories:
generation, field lookup, summarization, editing/extraction, and multi-turn Q&A.

### 4. Train

```bash
python llm/train_qlora.py \
    --train-file llm/data/chat/train.jsonl \
    --val-file   llm/data/chat/val.jsonl
```

Fine-tunes `unsloth/Qwen3-8B` (4-bit QLoRA) for 3 epochs.
Saves to `llm/checkpoints/run_001/`:
- `adapter/` — LoRA weights only
- `merged_16bit/` — full merged model for GGUF export

Optional flags:
```bash
--epochs 1              # quick smoke test
--max-seq-length 2048   # reduce if OOM (see hardware fallback)
--batch-size 1          # reduce if OOM
--wandb                 # enable W&B logging
```

### 5. Export to GGUF

```bash
python llm/export_to_gguf.py \
    --merged-model-dir llm/checkpoints/run_001/merged_16bit/
```

Produces `llm/exports/model.gguf` (Q4_K_M) and `llm/exports/Modelfile`.
The exact `ollama` commands are printed at the end.

---

## Ollama Testing

After step 5, the script prints the exact commands. They will look like:

```bash
ollama create tux-ai-chat -f llm/exports/Modelfile
ollama run tux-ai-chat
```

### Example prompts to try

```
Generate a customer record for a tech startup employee.
```

```
(paste a tokenized record)
What is the credit card token in this record?
```

```
(paste a tokenized record)
Summarize this in two sentences.
```

```
(paste a tokenized record)
Extract the Financial section as a bullet list.
```

```
Here is a record: (paste)
Now, what is the SSN token for this person?
```

---

## Hardware Fallback

If you get CUDA OOM errors, try in this order:

1. Reduce sequence length: `--max-seq-length 2048`
2. Reduce batch size: `--batch-size 1`
3. Switch to the 4B model:
   ```bash
   python llm/train_qlora.py --base-model unsloth/Qwen3-4B ...
   ```
   Qwen3-4B requires ~10 GB VRAM and fits on most 16 GB cards.
   The Modelfile template works unchanged (same `<|im_start|>`/`<|im_end|>` tokens).

---

## Qwen3 Thinking Mode

Qwen3 supports a dual thinking/non-thinking mode via special `<think>` tokens.

**Training**: thinking mode is disabled by passing `enable_thinking=False` to
`tokenizer.apply_chat_template(...)`. The model is trained only on direct responses.

**Inference with Ollama**: thinking mode remains off by default. If you want
step-by-step reasoning for a specific query, append `/think` to a user message:

```
Summarize this record. /think
(paste record)
```

To disable again: start a new session or prefix your message with `/no_think`.

---

## Quick Sanity Run (before scaling up)

```bash
python llm/generate_synthetic_docs.py --count 20
python llm/prepare_corpus.py
python llm/build_chat_dataset.py --examples-per-doc 4
python llm/train_qlora.py \
    --train-file llm/data/chat/train.jsonl \
    --val-file   llm/data/chat/val.jsonl \
    --epochs 1
```

---

## Important Notes

- `llm/data/raw_temp/` is auto-deleted by `prepare_corpus.py` and must not be committed.
- Model checkpoints, GGUF files, and tokenized data are all in `.gitignore`.
- The model is trained only on tokenized text. Raw PII never touches the training pipeline.
- Reverse-mapping (token → original value) is handled by the Redis layer in `src/redis_client.py` for authorized users only.
