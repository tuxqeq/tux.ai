"""
offline_rules.py — compare detector settings on SAVED predictions (no model run).

Input: a *_preds.jsonl written by eval_detector.py --save-preds (it stores Presidio and AI spans
with scores). For every combination of
  --presidio-thresholds   drop Presidio spans below this score (applied after Presidio's own
                          overlap dedupe, so it approximates HybridDetector(presidio_score_threshold))
  validate AI formats     hybrid_detect.validate_spans: off / drop / relabel / relabel_or_pii
  label rule              combine_union(tie_prefer="ai" | "presidio" | "ai_first")
it prints typed P/R/F1 and the privacy metrics, also with gold ORG moved to "ignore".
Use it on a DEV set to choose settings; report the chosen setting on the test set once.

Usage:
  .venv/bin/python eval/offline_rules.py --preds eval/results/detector_external_nemotron_dev_1000_<stamp>_preds.jsonl
"""
import argparse
import csv
import itertools
import json
import os
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "eval"))
import eval_detector as ev  # noqa: E402


def spans(text, raw):
    return [{"start": s, "end": e, "label": l, "source": src, "score": sc, "text": text[s:e]}
            for s, e, l, src, sc in raw]


def evaluate(rows, thr, validate, tie, ai_key, drop_org, hd):
    agg = ev.Aggregate()
    for r in rows:
        t = r["text"]
        gold = [tuple(g) for g in r["gold"]]
        ign = [tuple(i) for i in r.get("ignore", [])]
        if drop_org:
            ign += [g for g in gold if g[2] == "ORG"]
            gold = [g for g in gold if g[2] != "ORG"]
        pres = [p for p in spans(t, r["presidio"]) if p["score"] >= thr]
        ai = spans(t, r[ai_key])
        ai = hd.validate_spans(ai, t, validate)
        pred = [(x["start"], x["end"], ev.to_gold_label(x["label"], x["source"]))
                for x in hd.HybridDetector.combine_union(pres, ai, t, tie)]
        agg.add(ev.score_doc(t, gold, pred, ign), len(pred))
    return agg.summary()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preds", required=True)
    ap.add_argument("--ai-key", default="ai_word")
    ap.add_argument("--presidio-thresholds", default="0,0.3,0.4,0.5,0.6")
    ap.add_argument("--validate-modes", default="off,drop,relabel,relabel_or_pii")
    ap.add_argument("--ties", default="ai,presidio,ai_first")
    ap.add_argument("--out", default=None, help="CSV path (default: next to --preds)")
    args = ap.parse_args()
    import hybrid_detect as hd

    rows = [json.loads(line) for line in open(args.preds)]
    thrs = [float(x) for x in args.presidio_thresholds.split(",")]
    out_rows = []
    print(f"{len(rows)} texts from {args.preds}")
    print(f"{'pres_thr':>8} {'validate':>14} {'tie':>9} |{'P':>7}{'R':>7}{'F1':>7} |{'leak':>7}{'leakIn':>8}"
          f"{'leakIn-ORG':>11}{'spur':>6}")
    for thr, validate, tie in itertools.product(thrs, args.validate_modes.split(","), args.ties.split(",")):
        s = evaluate(rows, thr, validate, tie, args.ai_key, False, hd)
        s2 = evaluate(rows, thr, validate, tie, args.ai_key, True, hd)
        out_rows.append({"presidio_threshold": thr, "validate_ai": validate, "tie_prefer": tie,
                         "precision": s["micro_precision"], "recall": s["micro_recall"], "f1": s["micro_f1"],
                         "leaked_all": s["leaked_char_rate"], "leaked_our_types": s["leaked_char_rate_in_scope"],
                         "leaked_our_types_without_org": s2["leaked_char_rate_in_scope"],
                         "spurious": s["spurious_spans"]})
        print(f"{thr:>8.2f} {validate:>14} {tie:>9} |{s['micro_precision']:7.3f}{s['micro_recall']:7.3f}"
              f"{s['micro_f1']:7.3f} |{s['leaked_char_rate']:7.3f}{s['leaked_char_rate_in_scope']:8.3f}"
              f"{s2['leaked_char_rate_in_scope']:11.3f}{s['spurious_spans']:6}")
    out = args.out or args.preds.replace("_preds.jsonl", "_offline_rules.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
