"""
summarize_results.py — one markdown table from eval/results/detector_*.json.

For every (data set, model) the newest result file is used. Columns: typed P/R/F1 and the privacy
metrics (leaked chars of all PII, of our types, and of our types without ORG is not stored here —
use offline_rules.py for that).

Usage: .venv/bin/python eval/summarize_results.py [--modes presidio,ai_word,hybrid_word_union]
"""
import argparse
import glob
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="eval/results")
    ap.add_argument("--modes", default="presidio,ai_word,hybrid_word_union")
    args = ap.parse_args()
    newest = {}
    for f in sorted(glob.glob(os.path.join(args.dir, "detector_*.json"))):
        r = json.load(open(f))
        key = (r["meta"]["data"], r["meta"].get("model_path", "?"))
        if key not in newest or r["meta"]["created"] >= newest[key]["meta"]["created"]:
            newest[key] = r
    modes = args.modes.split(",")
    print("| Data set | Model | Mode | P | R | F1 | Entity recall | Full coverage | Leaked chars (all PII) | Leaked chars (our types) | Spurious |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for (data, model), r in sorted(newest.items()):
        for m in modes:
            if m not in r["results"]:
                continue
            s = r["results"][m]["summary"]
            li = s.get("leaked_char_rate_in_scope")
            print(f"| {os.path.basename(data)} | {os.path.basename(model)} | {m} | {s['micro_precision']:.3f} | "
                  f"{s['micro_recall']:.3f} | {s['micro_f1']:.3f} | {s['entity_recall_untyped']:.3f} | "
                  f"{s['full_coverage_untyped']:.3f} | {100 * s['leaked_char_rate']:.1f} % | "
                  f"{'-' if li is None else f'{100 * li:.1f} %'} | {s['spurious_spans']} |")


if __name__ == "__main__":
    main()
