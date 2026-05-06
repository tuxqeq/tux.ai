"""
train_qlora.py — Fine-tune Qwen3-8B as a chatbot using Unsloth + QLoRA.

Training targets assistant-only tokens (completion-only loss).
Thinking mode is disabled via enable_thinking=False in chat template application.

Usage:
    python llm/train_qlora.py \
        --train-file llm/data/chat/train.jsonl \
        --val-file   llm/data/chat/val.jsonl
"""

import argparse
import json
import logging
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "llm", "checkpoints", "run_001")
DEFAULT_BASE_MODEL = "unsloth/Qwen3-8B"


def _setup_logging(output_dir: str) -> logging.Logger:
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "training.log")
    logger = logging.getLogger("train_qlora")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def _load_jsonl(path: str) -> list[dict]:
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune Qwen3 chatbot on tokenized PII corpus via QLoRA."
    )
    parser.add_argument("--train-file", required=True, help="Path to train.jsonl")
    parser.add_argument("--val-file",   default=None,  help="Path to val.jsonl (optional)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL,
                        help=f"Unsloth model repo (default: {DEFAULT_BASE_MODEL})")
    parser.add_argument("--epochs",      type=int,   default=3)
    parser.add_argument("--lr",          type=float, default=2e-4)
    parser.add_argument("--batch-size",  type=int,   default=2)
    parser.add_argument("--grad-accum",  type=int,   default=4)
    parser.add_argument("--max-seq-length", type=int, default=4096,
                        help="Max token length per example. Reduce to 2048 if OOM.")
    parser.add_argument("--lora-rank",   type=int,   default=16)
    parser.add_argument("--lora-alpha",  type=int,   default=32)
    parser.add_argument("--seed",        type=int,   default=42)
    parser.add_argument("--wandb",       action="store_true",
                        help="Enable Weights & Biases logging")
    args = parser.parse_args()

    logger = _setup_logging(args.output_dir)
    logger.info("Starting QLoRA fine-tuning")
    logger.info(f"  Base model     : {args.base_model}")
    logger.info(f"  Output dir     : {args.output_dir}")
    logger.info(f"  Train file     : {args.train_file}")
    logger.info(f"  Val file       : {args.val_file}")
    logger.info(f"  Epochs         : {args.epochs}")
    logger.info(f"  Batch size     : {args.batch_size}  (grad_accum={args.grad_accum})")
    logger.info(f"  Max seq length : {args.max_seq_length}")
    logger.info(f"  LoRA rank/alpha: {args.lora_rank}/{args.lora_alpha}")

    if not args.wandb:
        os.environ["WANDB_DISABLED"] = "true"

    # ── 1. Load base model ─────────────────────────────────────────────────────
    logger.info("\nLoading base model via Unsloth...")
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logger.error("Unsloth not installed. Run: pip install unsloth")
        sys.exit(1)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        dtype=None,          # auto-detect bf16/fp16
        load_in_4bit=True,
        trust_remote_code=True,
    )

    # ── 2. Apply LoRA ──────────────────────────────────────────────────────────
    logger.info("Applying LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    # ── 3. Verify chat template ────────────────────────────────────────────────
    logger.info("\nVerifying Qwen3 chat template (enable_thinking=False)...")
    sample_msgs = [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    try:
        sample_rendered = tokenizer.apply_chat_template(
            sample_msgs,
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,
        )
        logger.info("Sample chat template output (first 300 chars):")
        logger.info(sample_rendered[:300])
    except TypeError:
        # Older tokenizer without enable_thinking — safe to ignore
        logger.warning(
            "tokenizer.apply_chat_template does not support enable_thinking; "
            "training without explicit flag. Verify no <think> tokens appear in output."
        )
        sample_rendered = tokenizer.apply_chat_template(
            sample_msgs, tokenize=False, add_generation_prompt=False
        )

    # Determine response template for completion-only loss
    RESPONSE_TEMPLATE = "<|im_start|>assistant\n"
    if RESPONSE_TEMPLATE not in sample_rendered:
        logger.warning(
            f"Response template '{RESPONSE_TEMPLATE}' not found in rendered sample. "
            "Check tokenizer.chat_template and update RESPONSE_TEMPLATE if needed."
        )

    # ── 4. Prepare dataset ─────────────────────────────────────────────────────
    logger.info("\nLoading and formatting dataset...")
    from datasets import Dataset

    def apply_template(example: dict) -> dict:
        messages = example["messages"]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=False,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
        return {"text": text}

    train_raw = _load_jsonl(args.train_file)
    train_ds  = Dataset.from_list(train_raw).map(apply_template, remove_columns=["messages"])

    val_ds = None
    if args.val_file and os.path.exists(args.val_file):
        val_raw = _load_jsonl(args.val_file)
        val_ds  = Dataset.from_list(val_raw).map(apply_template, remove_columns=["messages"])

    logger.info(f"Train examples: {len(train_ds)}")
    if val_ds:
        logger.info(f"Val examples  : {len(val_ds)}")

    # ── 5. Verify completion-only loss setup ────────────────────────────────────
    logger.info("\nSetting up completion-only loss (assistant tokens only)...")
    from trl import DataCollatorForCompletionOnlyLM

    response_template_ids = tokenizer.encode(
        RESPONSE_TEMPLATE, add_special_tokens=False
    )
    logger.info(
        f"Response template token IDs: {response_template_ids} "
        f"(decoded: {tokenizer.decode(response_template_ids)!r})"
    )

    data_collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template_ids,
        tokenizer=tokenizer,
    )

    # Quick sanity check: verify labels mask on first example
    sample_enc = tokenizer(
        train_ds[0]["text"],
        return_tensors="pt",
        max_length=args.max_seq_length,
        truncation=True,
    )
    sample_batch = data_collator([{"input_ids": sample_enc["input_ids"][0].tolist()}])
    labels = sample_batch["labels"][0].tolist()
    non_masked = sum(1 for l in labels if l != -100)
    total_tokens = len(labels)
    logger.info(
        f"Label check on first example: {non_masked}/{total_tokens} tokens have loss computed "
        f"({'OK' if non_masked > 0 else 'WARNING: all masked — check response template'})"
    )
    if non_masked == 0:
        logger.error(
            "All tokens are masked (label=-100). The response template may not match "
            f"the tokenizer output. RESPONSE_TEMPLATE={RESPONSE_TEMPLATE!r}\n"
            f"First 200 chars of rendered example: {train_ds[0]['text'][:200]}"
        )
        sys.exit(1)

    # ── 6. Configure trainer ───────────────────────────────────────────────────
    import torch
    from trl import SFTConfig, SFTTrainer

    bf16_supported = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    logger.info(f"\nbf16 supported: {bf16_supported}")

    eval_strategy = "steps" if val_ds else "no"

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        bf16=bf16_supported,
        fp16=not bf16_supported,
        logging_steps=10,
        save_steps=200,
        eval_steps=200 if val_ds else None,
        eval_strategy=eval_strategy,
        seed=args.seed,
        max_seq_length=args.max_seq_length,
        dataset_text_field="text",
        dataset_num_proc=2,
        packing=False,
        report_to="wandb" if args.wandb else "none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        args=sft_config,
        data_collator=data_collator,
    )

    # ── 7. Train ───────────────────────────────────────────────────────────────
    logger.info("\nStarting training...")
    train_result = trainer.train()

    train_loss = train_result.training_loss
    logger.info(f"\nTraining complete. Final train loss: {train_loss:.4f}")

    if val_ds:
        eval_result = trainer.evaluate()
        val_loss = eval_result.get("eval_loss", float("nan"))
        logger.info(f"Final val loss: {val_loss:.4f}")
    else:
        val_loss = None

    # ── 8. Save adapter ────────────────────────────────────────────────────────
    adapter_dir = os.path.join(args.output_dir, "adapter")
    logger.info(f"\nSaving LoRA adapter to {adapter_dir}")
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    # ── 9. Save merged 16-bit model ────────────────────────────────────────────
    merged_dir = os.path.join(args.output_dir, "merged_16bit")
    logger.info(f"Saving merged 16-bit model to {merged_dir}")
    model.save_pretrained_merged(
        merged_dir,
        tokenizer,
        save_method="merged_16bit",
    )

    print("\n" + "=" * 60)
    print(f"  Final train loss : {train_loss:.4f}")
    if val_loss is not None:
        print(f"  Final val loss   : {val_loss:.4f}")
    print(f"  Adapter saved    : {adapter_dir}")
    print(f"  Merged model     : {merged_dir}")
    print("=" * 60)
    print(f"\nNext step: python llm/export_to_gguf.py --merged-model-dir {merged_dir}")


if __name__ == "__main__":
    main()
