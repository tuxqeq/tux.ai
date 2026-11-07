"""
eval_detector.py — Phase 1: precision / recall / F1 of the PII detector on a labelled set.

Modes (each text is run through Presidio and the AI model once; hybrid = HybridDetector.combine,
the same rule that production detect() uses):
  presidio  rules only (Presidio built-ins + custom recognizers)
  ai        DistilBERT token classifier only, above --threshold
  hybrid    Presidio spans + AI spans where Presidio found nothing

Input: JSON list of {"text": str, "entities": [[start, end, LABEL], ...]} (generate_data.py format).
Gold labels: PER ORG LOC EMAIL PHONE SSN CREDIT_CARD DOB LICENSE PASSPORT IP_ADDRESS MRN
             BANK_ACCOUNT USERNAME VIN API_KEY MAC EMP_ID INSURANCE
Presidio labels are mapped to these with PRESIDIO_TO_GOLD; unmapped Presidio labels become OTHER.

Metrics
  typed (per label + micro): a prediction is a TP when it overlaps an unmatched gold span with the
      same label (one-to-one). "exact" also requires the same start/end (whitespace-trimmed).
  untyped (privacy view, label ignored):
      entity recall   gold entities touched by any prediction
      full coverage   gold entities whose every character is covered
      leaked chars    share of gold PII characters that no prediction covers
      spurious spans  predictions that touch no gold span

Usage
  python eval/eval_detector.py --data data/test_heldout_templates.json
  python eval/eval_detector.py --data data/train_data_v3.json --limit 5000      # in-distribution
  python eval/eval_detector.py --data data/test_heldout_templates.json --threshold 0.5
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

MODES = ("presidio", "ai", "hybrid")

PRESIDIO_TO_GOLD: Dict[str, str] = {
    "PERSON": "PER",
    "LOCATION": "LOC",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "US_SSN": "SSN",
    "CREDIT_CARD": "CREDIT_CARD",
    "DATE_OF_BIRTH": "DOB",
    "US_DRIVER_LICENSE": "LICENSE",
    "DRIVERS_LICENSE": "LICENSE",
    "US_PASSPORT": "PASSPORT",
    "PASSPORT_NUMBER": "PASSPORT",
    "IP_ADDRESS": "IP_ADDRESS",
    "MEDICAL_RECORD_NUMBER": "MRN",
    "US_BANK_NUMBER": "BANK_ACCOUNT",
    "BANK_ACCOUNT": "BANK_ACCOUNT",
    "USERNAME": "USERNAME",
    "VIN": "VIN",
    "API_KEY": "API_KEY",
    "SERVICE_API_KEY": "API_KEY",
    "AWS_KEY": "API_KEY",
    "MAC_ADDRESS": "MAC",
    "EMPLOYEE_ID": "EMP_ID",
    "INSURANCE_NUMBER": "INSURANCE",
}

Span = Tuple[int, int, str]  # start, end, label


def to_gold_label(label: str, source: str) -> str:
    if source == "PRESIDIO":
        return PRESIDIO_TO_GOLD.get(label, "OTHER")
    return label


def _overlap(a: Span, b: Span) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def _trim(text: str, s: int, e: int) -> Tuple[int, int]:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e


def score_doc(text: str, gold: List[Span], pred: List[Span]) -> dict:
    """Counts for one text. gold/pred = [(start, end, label)], labels already in the gold scheme."""
    out = {
        "tp": defaultdict(int), "fp": defaultdict(int), "fn": defaultdict(int),
        "tp_exact": defaultdict(int),
        "touched": defaultdict(int), "full": defaultdict(int), "support": defaultdict(int),
        "gold_chars": 0, "leaked_chars": 0, "spurious": 0, "fn_examples": [], "fp_examples": [],
    }
    # typed, one-to-one, overlap-based
    used = [False] * len(gold)
    for p in sorted(pred):
        hit = None
        for gi, g in enumerate(gold):
            if not used[gi] and g[2] == p[2] and _overlap(g, p):
                hit = gi
                break
        if hit is None:
            out["fp"][p[2]] += 1
            out["fp_examples"].append((text[p[0]:p[1]], p[2]))
        else:
            used[hit] = True
            out["tp"][p[2]] += 1
            g = gold[hit]
            if _trim(text, g[0], g[1]) == _trim(text, p[0], p[1]):
                out["tp_exact"][p[2]] += 1
    for gi, g in enumerate(gold):
        if not used[gi]:
            out["fn"][g[2]] += 1
            out["fn_examples"].append((text[g[0]:g[1]], g[2]))
    # untyped, privacy view
    covered = set()
    for p in pred:
        covered.update(range(p[0], p[1]))
    for g in gold:
        chars = set(range(g[0], g[1]))
        out["support"][g[2]] += 1
        out["gold_chars"] += len(chars)
        missed = len(chars - covered)
        out["leaked_chars"] += missed
        if missed < len(chars):
            out["touched"][g[2]] += 1
        if missed == 0:
            out["full"][g[2]] += 1
    out["spurious"] = sum(1 for p in pred if not any(_overlap(p, g) for g in gold))
    return out


def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


class Aggregate:
    def __init__(self):
        self.c = defaultdict(lambda: defaultdict(int))
        self.gold_chars = self.leaked_chars = self.spurious = self.n_pred = 0
        self.fn_examples: Dict[str, List[str]] = defaultdict(list)
        self.fp_examples: Dict[str, List[str]] = defaultdict(list)

    def add(self, d: dict, n_pred: int, keep: int = 15):
        for key in ("tp", "fp", "fn", "tp_exact", "touched", "full", "support"):
            for label, v in d[key].items():
                self.c[label][key] += v
        self.gold_chars += d["gold_chars"]
        self.leaked_chars += d["leaked_chars"]
        self.spurious += d["spurious"]
        self.n_pred += n_pred
        for t, label in d["fn_examples"]:
            if len(self.fn_examples[label]) < keep:
                self.fn_examples[label].append(t)
        for t, label in d["fp_examples"]:
            if len(self.fp_examples[label]) < keep:
                self.fp_examples[label].append(t)

    def rows(self) -> List[dict]:
        rows = []
        for label in sorted(self.c):
            c = self.c[label]
            p, r, f = _prf(c["tp"], c["fp"], c["fn"])
            _, _, fx = _prf(c["tp_exact"], c["fp"] + c["tp"] - c["tp_exact"], c["fn"] + c["tp"] - c["tp_exact"])
            sup = c["support"]
            rows.append({
                "label": label, "support": sup, "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                "precision": p, "recall": r, "f1": f, "f1_exact": fx,
                "entity_recall_untyped": c["touched"] / sup if sup else None,
                "full_coverage_untyped": c["full"] / sup if sup else None,
            })
        return rows

    def summary(self) -> dict:
        tp = sum(c["tp"] for c in self.c.values())
        fp = sum(c["fp"] for c in self.c.values())
        fn = sum(c["fn"] for c in self.c.values())
        tpx = sum(c["tp_exact"] for c in self.c.values())
        sup = sum(c["support"] for c in self.c.values())
        touched = sum(c["touched"] for c in self.c.values())
        full = sum(c["full"] for c in self.c.values())
        p, r, f = _prf(tp, fp, fn)
        _, _, fx = _prf(tpx, fp + tp - tpx, fn + tp - tpx)
        return {
            "gold_entities": sup, "predictions": self.n_pred,
            "micro_precision": p, "micro_recall": r, "micro_f1": f, "micro_f1_exact": fx,
            "entity_recall_untyped": touched / sup if sup else None,
            "full_coverage_untyped": full / sup if sup else None,
            "leaked_char_rate": self.leaked_chars / self.gold_chars if self.gold_chars else None,
            "spurious_spans": self.spurious,
        }


def _fmt(x) -> str:
    return "  -  " if x is None else f"{x:.3f}"


def print_report(mode: str, agg: Aggregate) -> None:
    s = agg.summary()
    print(f"\n=== {mode} ===")
    print(f"micro P {_fmt(s['micro_precision'])}  R {_fmt(s['micro_recall'])}  F1 {_fmt(s['micro_f1'])}"
          f"  (exact F1 {_fmt(s['micro_f1_exact'])})")
    print(f"privacy: entity recall {_fmt(s['entity_recall_untyped'])}  full coverage "
          f"{_fmt(s['full_coverage_untyped'])}  leaked chars {_fmt(s['leaked_char_rate'])}  "
          f"spurious spans {s['spurious_spans']}")
    print(f"{'label':<13}{'sup':>6}{'P':>7}{'R':>7}{'F1':>7}{'F1ex':>7}{'untypR':>8}")
    for r in agg.rows():
        print(f"{r['label']:<13}{r['support']:>6}{_fmt(r['precision']):>7}{_fmt(r['recall']):>7}"
              f"{_fmt(r['f1']):>7}{_fmt(r['f1_exact']):>7}{_fmt(r['entity_recall_untyped']):>8}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--model-path", default="models/pii_model_v3")
    ap.add_argument("--threshold", type=float, default=0.95, help="AI score threshold (production: 0.95)")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", default="eval/results")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            ap.error(f"unknown mode {m}; choose from {MODES}")
    data = json.load(open(args.data))
    if args.limit:
        data = data[: args.limit]

    from tqdm import tqdm
    from hybrid_detect import HybridDetector

    need_ai = any(m in ("ai", "hybrid") for m in modes)
    det = HybridDetector(ai_model_path=args.model_path, use_ai=need_ai, ai_threshold=args.threshold)

    aggs = {m: Aggregate() for m in modes}
    for item in tqdm(data, desc="Evaluating"):
        text = item["text"]
        gold = [(s, e, l) for s, e, l in item["entities"]]
        pres = det.detect_presidio(text) if any(m in ("presidio", "hybrid") for m in modes) else []
        ai = det.detect_ai(text) if need_ai else []
        by_mode = {"presidio": pres, "ai": ai, "hybrid": HybridDetector.combine(pres, ai)}
        for m in modes:
            pred = [(r["start"], r["end"], to_gold_label(r["label"], r["source"])) for r in by_mode[m]]
            aggs[m].add(score_doc(text, gold, pred), len(pred))

    for m in modes:
        print_report(m, aggs[m])

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    stem = f"detector_{os.path.splitext(os.path.basename(args.data))[0]}_{stamp}"
    meta = {"data": args.data, "n_texts": len(data), "model_path": args.model_path,
            "threshold": args.threshold, "modes": modes, "created": stamp,
            "presidio_to_gold": PRESIDIO_TO_GOLD}
    result = {"meta": meta, "results": {m: {"summary": aggs[m].summary(), "per_label": aggs[m].rows(),
                                             "fn_examples": aggs[m].fn_examples,
                                             "fp_examples": aggs[m].fp_examples} for m in modes}}
    with open(os.path.join(args.out_dir, stem + ".json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out_dir, stem + ".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mode"] + list(aggs[modes[0]].rows()[0].keys()) if aggs[modes[0]].rows() else ["mode"])
        w.writeheader()
        for m in modes:
            for r in aggs[m].rows():
                w.writerow({"mode": m, **r})
    print(f"\nSaved: {args.out_dir}/{stem}.json and .csv")


if __name__ == "__main__":
    main()
