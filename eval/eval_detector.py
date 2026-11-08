"""
eval_detector.py — Phase 1: precision / recall / F1 of the PII detector on a labelled set.

Modes (each text is run through Presidio and each AI granularity once):
  presidio           rules only (Presidio built-ins + custom recognizers)
  ai                 DistilBERT, HF pipeline over all sub-tokens (old), above --threshold
  hybrid             old rule (HybridDetector.combine): AI spans only where Presidio found nothing
  ai_word            DistilBERT, one label per whitespace word from its first sub-token (as trained)
  hybrid_union       union of Presidio + ai spans, label from the longest span, tie: AI
  hybrid_word        old rule with ai_word
  hybrid_word_union  union rule with ai_word  == production HybridDetector.detect() since 2026-11-07

Input: JSON list of {"text": str, "entities": [[start, end, LABEL], ...], "ignore": [...]?}
       (generate_data.py format; eval/prepare_external.py adds "ignore" and the OTHER label).
       ignore = spans that are not PII in scope (e.g. blood type): a prediction there that touches
       no gold span is neither a TP nor an FP. Gold label OTHER = PII without a type in our scheme:
       it counts in the privacy metrics, and its TP/FN are left out of the typed micro scores.
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

MODES = ("presidio", "ai", "hybrid", "ai_word", "hybrid_union", "hybrid_word", "hybrid_word_union")

from utils import PRESIDIO_TO_AI_LABEL  # noqa: E402

# Eval also scores AWS keys as API_KEY (the gold set has no AWS_KEY type).
PRESIDIO_TO_GOLD: Dict[str, str] = {**PRESIDIO_TO_AI_LABEL, "AWS_KEY": "API_KEY"}


Span = Tuple[int, int, str]  # start, end, label


def to_gold_label(label: str, source: str) -> str:
    if source == "PRESIDIO":
        return PRESIDIO_TO_GOLD.get(label, "OTHER")
    return "OTHER" if label == "PII" else label  # v4 generic PII label = gold OTHER


def _overlap(a: Span, b: Span) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def _trim(text: str, s: int, e: int) -> Tuple[int, int]:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e


def score_doc(text: str, gold: List[Span], pred: List[Span], ignore: List[Span] = ()) -> dict:
    """Counts for one text. gold/pred = [(start, end, label)], labels already in the gold scheme."""
    if ignore:
        pred = [p for p in pred
                if any(_overlap(p, g) for g in gold) or not any(_overlap(p, i) for i in ignore)]
    out = {
        "tp": defaultdict(int), "fp": defaultdict(int), "fn": defaultdict(int),
        "tp_exact": defaultdict(int),
        "touched": defaultdict(int), "full": defaultdict(int), "support": defaultdict(int),
        "gold_chars": 0, "leaked_chars": 0, "spurious": 0, "fn_examples": [], "fp_examples": [],
        "gold_chars_by": defaultdict(int), "leaked_chars_by": defaultdict(int),
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
        out["gold_chars_by"][g[2]] += len(chars)
        out["leaked_chars_by"][g[2]] += missed
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
        for label, v in d["gold_chars_by"].items():
            self.c[label]["gold_chars"] += v
        for label, v in d["leaked_chars_by"].items():
            self.c[label]["leaked_chars"] += v
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
                "leaked_char_rate": c["leaked_chars"] / c["gold_chars"] if c["gold_chars"] else None,
            })
        return rows

    def summary(self) -> dict:
        typed = [c for label, c in self.c.items() if label != "OTHER"]  # untyped PII: no TP/FN here
        tp = sum(c["tp"] for c in typed)
        fp = sum(c["fp"] for c in self.c.values())
        fn = sum(c["fn"] for c in typed)
        tpx = sum(c["tp_exact"] for c in typed)
        sup = sum(c["support"] for c in self.c.values())
        touched = sum(c["touched"] for c in self.c.values())
        full = sum(c["full"] for c in self.c.values())
        p, r, f = _prf(tp, fp, fn)
        _, _, fx = _prf(tpx, fp + tp - tpx, fn + tp - tpx)
        gc_in = sum(c["gold_chars"] for c in typed)
        lc_in = sum(c["leaked_chars"] for c in typed)
        return {
            "gold_entities": sup, "predictions": self.n_pred,
            "micro_precision": p, "micro_recall": r, "micro_f1": f, "micro_f1_exact": fx,
            "entity_recall_untyped": touched / sup if sup else None,
            "full_coverage_untyped": full / sup if sup else None,
            "leaked_char_rate": self.leaked_chars / self.gold_chars if self.gold_chars else None,
            "leaked_char_rate_in_scope": lc_in / gc_in if gc_in else None,
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
          f"{_fmt(s['full_coverage_untyped'])}  leaked chars {_fmt(s['leaked_char_rate'])} "
          f"(our types {_fmt(s['leaked_char_rate_in_scope'])})  "
          f"spurious spans {s['spurious_spans']}")
    print(f"{'label':<13}{'sup':>6}{'P':>7}{'R':>7}{'F1':>7}{'F1ex':>7}{'untypR':>8}{'leaked':>8}")
    for r in agg.rows():
        print(f"{r['label']:<13}{r['support']:>6}{_fmt(r['precision']):>7}{_fmt(r['recall']):>7}"
              f"{_fmt(r['f1']):>7}{_fmt(r['f1_exact']):>7}{_fmt(r['entity_recall_untyped']):>8}"
              f"{_fmt(r['leaked_char_rate']):>8}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--model-path", default="models/pii_model_v4")
    ap.add_argument("--threshold", type=float, default=0.95, help="AI score threshold (production: 0.95)")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", default="eval/results")
    ap.add_argument("--presidio-threshold", type=float, default=0.0,
                    help="drop Presidio results below this score (production default: 0.0)")
    ap.add_argument("--validate-ai", default="off", choices=["off", "drop", "relabel", "relabel_or_pii"],
                    help="format checks on structured AI labels (hybrid_detect.validate_spans)")
    ap.add_argument("--save-preds", action="store_true",
                    help="also write every text's gold and raw predictions to <stem>_preds.jsonl")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            ap.error(f"unknown mode {m}; choose from {MODES}")
    data = json.load(open(args.data))
    if args.limit:
        data = data[: args.limit]

    try:
        from tqdm import tqdm
        from hybrid_detect import HybridDetector
    except ModuleNotFoundError as exc:
        sys.exit(f"{exc}. Run with the project venv: source .venv/bin/activate (or .venv/bin/python ...)")

    need_pres = any(m == "presidio" or m.startswith("hybrid") for m in modes)
    need_sub = any(m in ("ai", "hybrid", "hybrid_union") for m in modes)
    need_word = any(m in ("ai_word", "hybrid_word", "hybrid_word_union") for m in modes)
    det = HybridDetector(ai_model_path=args.model_path, use_ai=need_sub or need_word,
                         ai_threshold=args.threshold, presidio_score_threshold=args.presidio_threshold,
                         validate_ai_formats=False if args.validate_ai == "off" else args.validate_ai)

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    stem = f"detector_{os.path.splitext(os.path.basename(args.data))[0]}_{stamp}"
    preds_f = open(os.path.join(args.out_dir, stem + "_preds.jsonl"), "w") if args.save_preds else None
    raw = lambda rs: [[r["start"], r["end"], r["label"], r["source"], float(r["score"])] for r in rs]

    aggs = {m: Aggregate() for m in modes}
    for item in tqdm(data, desc="Evaluating"):
        text = item["text"]
        gold = [(s, e, l) for s, e, l in item["entities"]]
        ignore = [(s, e, l) for s, e, l in item.get("ignore", [])]
        pres = det.detect_presidio(text) if need_pres else []
        ai = det.detect_ai(text) if need_sub else []
        aiw = det.detect_ai(text, granularity="word") if need_word else []
        by_mode = {
            "presidio": pres,
            "ai": ai,
            "hybrid": HybridDetector.combine(pres, ai),
            "ai_word": aiw,
            "hybrid_union": HybridDetector.combine_union(pres, ai, text),
            "hybrid_word": HybridDetector.combine(pres, aiw),
            "hybrid_word_union": HybridDetector.combine_union(pres, aiw, text),
        }
        for m in modes:
            pred = [(r["start"], r["end"], to_gold_label(r["label"], r["source"])) for r in by_mode[m]]
            aggs[m].add(score_doc(text, gold, pred, ignore), len(pred))
        if preds_f:
            preds_f.write(json.dumps({"text": text, "gold": item["entities"], "ignore": item.get("ignore", []),
                                      "presidio": raw(pres),
                                      "ai": raw(ai), "ai_word": raw(aiw)}, ensure_ascii=False) + "\n")
    if preds_f:
        preds_f.close()

    for m in modes:
        print_report(m, aggs[m])

    print(f"\n{'mode':<19}{'P':>7}{'R':>7}{'F1':>7}{'F1ex':>7}{'untypR':>8}{'full':>7}{'leaked':>8}{'leakIn':>8}{'spur':>6}")
    for m in modes:
        x = aggs[m].summary()
        print(f"{m:<19}{_fmt(x['micro_precision']):>7}{_fmt(x['micro_recall']):>7}{_fmt(x['micro_f1']):>7}"
              f"{_fmt(x['micro_f1_exact']):>7}{_fmt(x['entity_recall_untyped']):>8}"
              f"{_fmt(x['full_coverage_untyped']):>7}{_fmt(x['leaked_char_rate']):>8}"
              f"{_fmt(x['leaked_char_rate_in_scope']):>8}{x['spurious_spans']:>6}")

    meta = {"data": args.data, "n_texts": len(data), "model_path": args.model_path,
            "threshold": args.threshold, "presidio_threshold": args.presidio_threshold,
            "validate_ai": args.validate_ai, "modes": modes, "created": stamp,
            "presidio_to_gold": PRESIDIO_TO_GOLD}
    result = {"meta": meta, "results": {m: {"summary": aggs[m].summary(), "per_label": aggs[m].rows(),
                                             "fn_examples": aggs[m].fn_examples,
                                             "fp_examples": aggs[m].fp_examples} for m in modes}}
    with open(os.path.join(args.out_dir, stem + ".json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    fields = ["mode", "label", "support", "tp", "fp", "fn", "precision", "recall", "f1", "f1_exact",
              "entity_recall_untyped", "full_coverage_untyped", "leaked_char_rate"]
    with open(os.path.join(args.out_dir, stem + ".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in modes:
            for r in aggs[m].rows():
                w.writerow({"mode": m, **r})
    print(f"\nSaved: {args.out_dir}/{stem}.json and .csv" + (" and _preds.jsonl" if preds_f else ""))


if __name__ == "__main__":
    main()
