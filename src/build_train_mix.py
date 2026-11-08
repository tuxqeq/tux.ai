"""
build_train_mix.py — training data for pii_model_v4: Nemotron-PII documents + Faker templates.

Why: pii_model_v3 was trained only on 257 one-sentence Faker templates and drops from F1 0.977
(held-out templates) to 0.499 on Nemotron-PII documents (thesis decision log, 1d).

What it writes
  data/train_data_v4.json             training items {"text", "entities": [[start, end, LABEL]]}
  data/external_nemotron_dev_1000.json  dev set in eval format (for tuning validators, tie-break,
                                       Presidio fixes); disjoint from the training documents
Nemotron documents come from the TRAIN split only; the 1,000-document test sample
(data/external_nemotron_test_1000.json) stays untouched for the final report.

Labels: eval/prepare_external.convert() (same buckets as the evaluation). Our 19 types are kept;
OTHER (passwords, cookies, PINs, ...) becomes the new generic label PII; IGNORE spans become O.
Documents are cut into the same windows as inference (hybrid_detect.word_windows: line breaks,
<= 32 words); entity spans are clipped to each window.

Usage (on the Mac):
  .venv/bin/python src/build_train_mix.py                 # 8,000 docs + 50,000 template sentences
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "eval"))
sys.path.insert(0, os.path.join(_ROOT, "src"))
from prepare_external import convert, parse_spans  # noqa: E402
from hybrid_detect import word_windows  # noqa: E402

_WORD_RE = re.compile(r"\S+")


def doc_to_windows(text, gold, max_words):
    words = [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]
    items = []
    for win in word_windows(text, words, max_words):
        ws, we = words[win[0]][0], words[win[-1]][1]
        ents = []
        for s, e, label in gold:
            s2, e2 = max(s, ws), min(e, we)
            if s2 < e2:
                ents.append([s2 - ws, e2 - ws, "PII" if label == "OTHER" else label])
        items.append({"text": text[ws:we], "entities": ents})
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nemotron-docs", type=int, default=8000)
    ap.add_argument("--dev-docs", type=int, default=1000)
    ap.add_argument("--template-file", default="data/train_data_v3.json")
    ap.add_argument("--template-samples", type=int, default=50000)
    ap.add_argument("--max-words", type=int, default=32)
    ap.add_argument("--max-length", type=int, default=128, help="only for the truncation report")
    ap.add_argument("--tokenizer", default="models/pii_model_v3")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/train_data_v4.json")
    ap.add_argument("--dev-out", default="data/external_nemotron_dev_1000.json")
    args = ap.parse_args()

    from datasets import load_dataset
    ds = load_dataset("nvidia/Nemotron-PII", split="train")
    order = list(range(len(ds)))
    random.Random(args.seed).shuffle(order)
    dev_idx = order[: args.dev_docs]
    train_idx = order[args.dev_docs: args.dev_docs + args.nemotron_docs]

    stats = Counter()
    dev = []
    for i in dev_idx:
        row = ds[i]
        gold, ignore = convert(row["text"], parse_spans(row["spans"]), stats)
        dev.append({"text": row["text"], "entities": gold, "ignore": ignore, "uid": row.get("uid"),
                    "domain": row.get("domain"), "document_type": row.get("document_type"),
                    "document_format": row.get("document_format")})

    nemo = []
    for i in train_idx:
        row = ds[i]
        gold, _ = convert(row["text"], parse_spans(row["spans"]), stats)
        nemo.extend(doc_to_windows(row["text"], gold, args.max_words))

    templates = json.load(open(args.template_file))
    rng = random.Random(args.seed)
    templates = rng.sample(templates, min(args.template_samples, len(templates)))

    mix = nemo + templates
    rng.shuffle(mix)
    json.dump(mix, open(args.out, "w"), ensure_ascii=False)
    json.dump(dev, open(args.dev_out, "w"), ensure_ascii=False)

    labels = Counter(e[2] for x in mix for e in x["entities"])
    neg = sum(1 for x in nemo if not x["entities"]) / max(1, len(nemo))
    print(f"Nemotron train split: {len(ds)} docs; used {len(train_idx)} for training, {len(dev_idx)} for dev")
    print(f"training items: {len(mix)} = {len(nemo)} Nemotron windows ({neg:.0%} without entities) "
          f"+ {len(templates)} template sentences")
    print(f"labels: {dict(labels.most_common())}")
    print(f"conversion stats: {dict(stats)}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    sample = rng.sample(mix, min(20000, len(mix)))
    lens = sorted(len(tok(_WORD_RE.findall(x["text"]), is_split_into_words=True)["input_ids"]) for x in sample)
    over = sum(1 for n in lens if n > args.max_length) / len(lens)
    print(f"tokens per item (sample of {len(lens)}): p50 {lens[len(lens) // 2]}, p95 {lens[int(len(lens) * .95)]}, "
          f"p99 {lens[int(len(lens) * .99)]}, max {lens[-1]}; over {args.max_length}: {over:.2%}")
    print(f"wrote {args.out} and {args.dev_out}")


if __name__ == "__main__":
    main()
