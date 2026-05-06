"""
build_chat_dataset.py — Convert tokenized documents into multi-turn chat training examples.

Produces JSONL files in the format:
  {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}, ...]}

Five conversation categories per training example (sampled per document):
  1. Generation   — model emits a full tokenized record
  2. Field lookup — model answers a question about a specific placeholder
  3. Summarization — model summarizes while preserving all placeholders
  4. Editing/transformation — model reformats or extracts a section
  5. Cross-record multi-turn — two-turn conversation about a pasted record
"""

import argparse
import json
import os
import random
import re
import sys
from typing import Any

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INPUT_DIR = os.path.join(_REPO_ROOT, "llm", "data", "tokenized")
DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "llm", "data", "chat")

SYSTEM_PROMPT = (
    "You are a document assistant trained on tokenized records. "
    "Personally identifiable information appears as placeholder tokens in the format "
    "`[TYPE_hash]` (for example `[PERSON_a1b2c3d4]`, `[SSN_e5f6g7h8]`). "
    "Always preserve this exact format in your responses. "
    "Never invent untokenized PII. Never attempt to decode placeholders."
)

# --- Record type labels inferred from filename prefix ---
_TYPE_LABELS = {
    "personal_banking":        "Personal Banking Customer",
    "intl_business":           "International Business Client",
    "gov_contractor":          "Government Contractor",
    "healthcare_professional": "Healthcare Professional",
    "tech_startup":            "Tech Startup Employee",
}


def _infer_record_type(filename: str) -> str:
    for prefix, label in _TYPE_LABELS.items():
        if filename.startswith(prefix):
            return label
    return "customer"


def _extract_tokens(text: str) -> list[str]:
    return re.findall(r"\[[A-Z_]+_[0-9a-f]{8}\]", text)


def _extract_field_tokens(text: str) -> list[tuple[str, str]]:
    """Return (field_name, token) pairs where field_name is the word before the token."""
    pairs = []
    for match in re.finditer(r"([A-Za-z ]+):\s*(\[[A-Z_]+_[0-9a-f]{8}\])", text):
        field = match.group(1).strip().split("\n")[-1].strip("- ")
        token = match.group(2)
        if field and token:
            pairs.append((field, token))
    return pairs


def _first_n_lines(text: str, n: int = 8) -> str:
    return "\n".join(text.splitlines()[:n])


# ─────────────────────────── Template functions ───────────────────────────────

def tmpl_generation(doc: str, record_type: str, rng: random.Random) -> list[dict]:
    prompts = [
        f"Generate a customer record for a {record_type}.",
        f"Create a sample {record_type} profile with all relevant fields.",
        f"Produce a complete {record_type} record in the standard format.",
        f"Write a {record_type} entry for the database.",
    ]
    user_msg = rng.choice(prompts)
    return [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": user_msg},
        {"role": "assistant", "content": doc.strip()},
    ]


def tmpl_field_lookup(doc: str, record_type: str, rng: random.Random) -> list[dict] | None:
    pairs = _extract_field_tokens(doc)
    if not pairs:
        return None
    field, token = rng.choice(pairs)
    token_type = token.split("_")[0].strip("[")

    question_variants = [
        f"What is the {field} in this record?\n\n{doc.strip()}",
        f"Find the {field} value from the following {record_type} record:\n\n{doc.strip()}",
        f"What {field} is listed in this profile?\n\n{doc.strip()}",
        f"Extract the {field} from this record:\n\n{doc.strip()}",
    ]
    answer_variants = [
        f"The {field} is `{token}`.",
        f"The {field} value is `{token}`.",
        f"`{token}` is the {field}.",
    ]
    return [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": rng.choice(question_variants)},
        {"role": "assistant", "content": rng.choice(answer_variants)},
    ]


def tmpl_summarization(doc: str, record_type: str, rng: random.Random) -> list[dict]:
    tokens = _extract_tokens(doc)
    token_sample = tokens[:3] if tokens else []
    token_refs = ", ".join(f"`{t}`" for t in token_sample)
    placeholder_note = (
        f" Key identifiers include {token_refs} and others."
        if token_refs else ""
    )

    question_variants = [
        f"Summarize this {record_type} record in two sentences.\n\n{doc.strip()}",
        f"Give me a brief two-sentence summary of the following record:\n\n{doc.strip()}",
        f"Provide a concise summary of this profile in two sentences:\n\n{doc.strip()}",
    ]

    # Build a generic two-sentence summary referencing real tokens
    if tokens:
        t1 = tokens[0]
        t2 = tokens[1] if len(tokens) > 1 else tokens[0]
        summary_variants = [
            (
                f"This record contains a {record_type} identified by `{t1}` "
                f"with associated credentials and financial identifiers including `{t2}`."
                f"{placeholder_note} "
                f"All personally identifiable information has been replaced with "
                f"placeholder tokens of the form `[TYPE_hash]`."
            ),
            (
                f"The {record_type} profile includes placeholder `{t1}` as the primary identifier "
                f"alongside multiple other tokenized fields such as `{t2}`."
                f" No raw PII is present in this record — all values are represented as tokens."
            ),
        ]
    else:
        summary_variants = [
            (
                f"This {record_type} record contains multiple sections including "
                "financial, medical, and employment information. "
                "All personally identifiable information has been replaced with `[TYPE_hash]` placeholders."
            ),
        ]
    return [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": rng.choice(question_variants)},
        {"role": "assistant", "content": rng.choice(summary_variants)},
    ]


def tmpl_editing(doc: str, record_type: str, rng: random.Random) -> list[dict] | None:
    # Identify sections by header lines
    lines = doc.splitlines()
    sections: dict[str, list[str]] = {}
    current = "header"
    for line in lines:
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("-") and len(stripped) < 40:
            current = stripped.rstrip(":")
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)

    if len(sections) < 2:
        return None

    section_name = rng.choice([k for k in sections if k != "header"])
    section_lines = [l for l in sections[section_name] if l.strip()]

    if not section_lines:
        return None

    bullet_list = "\n".join(
        f"- {l.strip().lstrip('- ')}" for l in section_lines if l.strip()
    )

    question_variants = [
        f"Extract just the {section_name} section as a bullet list from this record:\n\n{doc.strip()}",
        f"From this {record_type} profile, pull out the {section_name} section formatted as bullets:\n\n{doc.strip()}",
        f"Give me the {section_name} information only, as a bullet list:\n\n{doc.strip()}",
    ]
    return [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": rng.choice(question_variants)},
        {"role": "assistant", "content": f"**{section_name}:**\n\n{bullet_list}"},
    ]


def tmpl_cross_record(doc: str, record_type: str, rng: random.Random) -> list[dict] | None:
    pairs = _extract_field_tokens(doc)
    tokens = _extract_tokens(doc)

    if not pairs or not tokens:
        return None

    field1, token1 = rng.choice(pairs)
    remaining = [p for p in pairs if p[1] != token1]
    if not remaining:
        return None
    field2, token2 = rng.choice(remaining)

    intro_variants = [
        f"I have a {record_type} record I'd like to ask you about:\n\n{doc.strip()}",
        f"Here's a tokenized {record_type} profile:\n\n{doc.strip()}",
        f"Please review this {record_type} record:\n\n{doc.strip()}",
    ]
    follow_up_variants = [
        f"What is the {field2} for this person?",
        f"Can you tell me the {field2} from that record?",
        f"Now, what does the record show for {field2}?",
    ]
    answer_variants = [
        f"The {field2} from that record is `{token2}`.",
        f"According to the record, the {field2} is `{token2}`.",
        f"`{token2}` is the {field2} for this individual.",
    ]
    return [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": rng.choice(intro_variants)},
        {"role": "assistant", "content": f"Understood. I can see the {record_type} record with `{token1}` as the {field1} and other tokenized fields. What would you like to know?"},
        {"role": "user",      "content": rng.choice(follow_up_variants)},
        {"role": "assistant", "content": rng.choice(answer_variants)},
    ]


_TEMPLATES = [
    tmpl_generation,
    tmpl_field_lookup,
    tmpl_summarization,
    tmpl_editing,
    tmpl_cross_record,
]


def generate_examples(
    doc: str,
    filename: str,
    examples_per_doc: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    record_type = _infer_record_type(os.path.basename(filename))
    examples = []

    # Always include one generation example
    examples.append({"messages": tmpl_generation(doc, record_type, rng)})

    # Sample the rest from all templates
    remaining_budget = examples_per_doc - 1
    template_pool = list(_TEMPLATES) * 3  # allow repeats
    rng.shuffle(template_pool)

    for tmpl_fn in template_pool:
        if len(examples) >= examples_per_doc:
            break
        result = tmpl_fn(doc, record_type, rng)
        if result is not None:
            examples.append({"messages": result})

    return examples[:examples_per_doc]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build multi-turn chat dataset from tokenized documents."
    )
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--examples-per-doc", type=int, default=6)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    if not os.path.isdir(args.input_dir):
        print(f"ERROR: Input directory not found: {args.input_dir}")
        sys.exit(1)

    txt_files = sorted(
        os.path.join(args.input_dir, f)
        for f in os.listdir(args.input_dir)
        if f.endswith(".txt")
    )

    if not txt_files:
        print(f"No .txt files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(txt_files)} tokenized documents in {args.input_dir}")

    all_examples: list[dict] = []
    for fpath in txt_files:
        with open(fpath, "r", encoding="utf-8") as f:
            doc = f.read()
        examples = generate_examples(doc, fpath, args.examples_per_doc, rng)
        all_examples.extend(examples)

    rng.shuffle(all_examples)
    split_idx = max(1, int(len(all_examples) * (1 - args.val_split)))
    train_examples = all_examples[:split_idx]
    val_examples   = all_examples[split_idx:]

    train_path = os.path.join(args.output_dir, "train.jsonl")
    val_path   = os.path.join(args.output_dir, "val.jsonl")

    with open(train_path, "w", encoding="utf-8") as f:
        for ex in train_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for ex in val_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\nDataset statistics:")
    print(f"  Total examples : {len(all_examples)}")
    print(f"  Train          : {len(train_examples)}  → {train_path}")
    print(f"  Validation     : {len(val_examples)}   → {val_path}")
    print(f"  Examples/doc   : {args.examples_per_doc}")


if __name__ == "__main__":
    main()
