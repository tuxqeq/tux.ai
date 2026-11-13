"""
eval_llm.py — LLM evaluation of thesis decision D-30: where should the model get its knowledge
of the records from?

  A0  base instruct model, no retrieval          (what the prototype had: nothing to answer from)
  A   closed-book fine-tuned model, no retrieval (knowledge in the weights)
  B   base instruct model + RAG                  (knowledge in the index; the shipped design, D-23)
  C   fine-tuned model + RAG                     (both)

The questions come from llm/build_qa_dataset.py (eval/llm_eval_set.jsonl) and are already
tokenized, i.e. they are what the chat path sends to the model after detection.

Scores per question (no LLM judge; string checks only):
  E1/E2  correct      the expected token, with brackets, is in the answer
         abstained    not correct and the answer says "no record"/"cannot find"/...
         wrong        not correct and not abstained
  E3     correct      abstained and no token other than the asked person's
  all    invented     the answer has a token that is not in the dataset (not in the token map) —
                      such a token cannot be decrypted and is a fabricated identifier
  E4     leaked       the plaintext value of an identifier the detector missed is in the answer
  E5     recall / precision of the PERSON tokens listed

  # one config (the Ollama model must exist)
  python eval/eval_llm.py --config B --model qwen3:4b-instruct-2507-q4_K_M \
      --dataset-id 99e90879-0058-40bc-b2d0-338e0ea5986f
  # table over all result files
  python eval/eval_llm.py --summarize
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TOKEN_RE = re.compile(r"\[[A-Z_]+_[0-9a-f]{12,16}\]")
HEX_RE = re.compile(r"_([0-9a-f]{12,16})\]")
ABSTAIN_RE = re.compile(
    r"no record|cannot find|can't find|could not find|couldn't find|unable to (?:find|locate)|"
    r"not (?:found|available|present|listed|included|mentioned|provided)|"
    r"no (?:information|matching|data|such|details)|"
    r"(?:do|does) not (?:have|contain|appear|include)|don't have|doesn't (?:have|contain|appear)|"
    r"there is no", re.I)
THINK_RE = re.compile(r"<think>.*?</think>", re.S)
RESULTS_DIR = os.path.join(ROOT, "eval", "results")


def corpus_tokens(corpus_dir: str) -> set:
    toks = set()
    for f in os.listdir(corpus_dir):
        if f.endswith(".txt"):
            toks.update(TOKEN_RE.findall(open(os.path.join(corpus_dir, f), encoding="utf-8").read()))
    return toks


def ollama_chat(url: str, model: str, system: str, user: str, num_predict: int, num_ctx: int) -> dict:
    body = {"model": model, "stream": False, "keep_alive": "15m",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "seed": 0, "num_predict": num_predict, "num_ctx": num_ctx}}
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def score(q: dict, answer: str, known: set) -> dict:
    out = TOKEN_RE.findall(answer)
    subject = q.get("subject")
    others = [t for t in out if t != subject]
    s = {"invented": sorted({t for t in others if t not in known}),
         "abstained": bool(ABSTAIN_RE.search(answer))}
    kind = q["kind"]
    if kind in ("E1_known", "E2_new"):
        exp = q["expected_token"]
        s["correct"] = exp in answer
        s["correct_loose"] = HEX_RE.search(exp).group(1) in answer
        s["abstained"] = s["abstained"] and not s["correct"]
        s["wrong"] = not s["correct"] and not s["abstained"]
    elif kind == "E3_absent":
        s["correct"] = s["abstained"] and not others
        s["answered_anyway"] = bool(others)
    elif kind == "E4_leak":
        s["leaked"] = q["plaintext_value"].lower() in answer.lower()
    elif kind == "E5_list":
        found = {t for t in out if t.startswith("[PERSON_")}
        exp = set(q["expected_tokens"])
        hit = len(found & exp)
        s["recall"] = hit / len(exp) if exp else 0.0
        s["precision"] = hit / len(found) if found else 0.0
        s["listed"] = len(found)
    return s


def run(args) -> None:
    from llm.build_qa_dataset import SYSTEM_PROMPT_A
    questions = [json.loads(l) for l in open(args.eval_file, encoding="utf-8")]
    if args.kinds:
        questions = [q for q in questions if q["kind"] in args.kinds.split(",")]
    if args.limit:
        questions = questions[:args.limit]
    known = corpus_tokens(args.corpus_dir)
    retriever = None
    if args.config in ("B", "C"):
        from api.services import rag
        retriever = rag.Retriever(args.chroma_path)
        if not retriever.has_index(args.dataset_id):
            sys.exit(f"no RAG index for dataset {args.dataset_id} in {args.chroma_path}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    done = set()
    if os.path.exists(args.out) and not args.fresh:
        done = {json.loads(l)["id"] for l in open(args.out, encoding="utf-8")}
    with open(args.out, "a" if done else "w", encoding="utf-8") as f:
        for i, q in enumerate(questions):
            if q["id"] in done:
                continue
            t0 = time.time()
            retrieved_hit = None
            if retriever is not None:
                records = retriever.retrieve(args.dataset_id, q["question"], args.k)
                system = rag.build_system_prompt(records)
                ctx = "\n".join(r["text"] for r in records)
                if "expected_token" in q:
                    retrieved_hit = q["expected_token"] in ctx
                elif q["kind"] == "E4_leak":
                    retrieved_hit = q["plaintext_value"] in ctx
            else:
                system = SYSTEM_PROMPT_A
            t1 = time.time()
            resp = ollama_chat(args.ollama_url, args.model, system, q["question"], args.num_predict
                               if q["kind"] != "E5_list" else args.num_predict * 4, args.num_ctx)
            answer = THINK_RE.sub("", resp.get("message", {}).get("content", "")).strip()
            row = {"id": q["id"], "kind": q["kind"], "config": args.config, "model": args.model,
                   "question": q["question"], "answer": answer, "retrieved_hit": retrieved_hit,
                   "retrieval_s": round(t1 - t0, 3), "llm_s": round(time.time() - t1, 3),
                   "prompt_tokens": resp.get("prompt_eval_count"), "output_tokens": resp.get("eval_count")}
            row.update(score(q, answer, known))
            f.write(json.dumps(row) + "\n")
            f.flush()
            if (i + 1) % 25 == 0:
                print(f"{args.config}: {i + 1}/{len(questions)}", flush=True)
    print(f"done: {args.out}")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summarize(results_dir: str) -> str:
    rows = defaultdict(list)
    for fn in sorted(os.listdir(results_dir)):
        if fn.startswith("llm_") and fn.endswith(".jsonl"):
            for l in open(os.path.join(results_dir, fn), encoding="utf-8"):
                r = json.loads(l)
                rows[(r["config"], r["kind"])].append(r)
    configs = sorted({c for c, _ in rows})
    lines = ["| Config | Set | n | Correct | Abstained | Wrong | Invented token | Leaked | Retrieval hit | LLM s/q |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    summary = {}
    pct = lambda v: "–" if v is None else f"{100 * v:.1f} %"
    for c in configs:
        for kind in ("E1_known", "E2_new", "E3_absent", "E4_leak", "E5_list"):
            rs = rows.get((c, kind))
            if not rs:
                continue
            m = {"n": len(rs),
                 "correct": _mean([float(r["correct"]) for r in rs if "correct" in r]),
                 "abstained": _mean([float(r["abstained"]) for r in rs]),
                 "wrong": _mean([float(r["wrong"]) for r in rs if "wrong" in r]),
                 "invented": _mean([float(bool(r["invented"])) for r in rs]),
                 "leaked": _mean([float(r["leaked"]) for r in rs if "leaked" in r]),
                 "retrieved_hit": _mean([float(r["retrieved_hit"]) for r in rs if r.get("retrieved_hit") is not None]),
                 "recall": _mean([r["recall"] for r in rs if "recall" in r]),
                 "precision": _mean([r["precision"] for r in rs if "precision" in r]),
                 "llm_s": _mean([r["llm_s"] for r in rs])}
            summary[f"{c}/{kind}"] = m
            corr = m["correct"] if kind != "E5_list" else m["recall"]
            lines.append(f"| {c} | {kind} | {m['n']} | {pct(corr)}{' (recall)' if kind == 'E5_list' else ''} | "
                         f"{pct(m['abstained'])} | {pct(m['wrong'])} | {pct(m['invented'])} | {pct(m['leaked'])} | "
                         f"{pct(m['retrieved_hit'])} | {m['llm_s']:.2f} |")
    json.dump(summary, open(os.path.join(results_dir, "summary.json"), "w"), indent=1)
    table = "\n".join(lines)
    open(os.path.join(results_dir, "summary.md"), "w").write(table + "\n")
    return table


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", choices=["A0", "A", "B", "C"])
    ap.add_argument("--model")
    ap.add_argument("--dataset-id")
    ap.add_argument("--eval-file", default=os.path.join(ROOT, "eval", "llm_eval_set.jsonl"))
    ap.add_argument("--corpus-dir", default=os.path.join(ROOT, "llm", "data", "tokenized_v2"))
    ap.add_argument("--chroma-path", default=os.path.join(ROOT, "data", "chroma"))
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--num-predict", type=int, default=200)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--kinds", help="comma-separated subset, e.g. E1_known,E3_absent")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out")
    ap.add_argument("--fresh", action="store_true", help="overwrite instead of resuming")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()
    if args.summarize:
        print(summarize(RESULTS_DIR))
        return
    if not args.config or not args.model:
        ap.error("--config and --model are required")
    if args.config in ("B", "C") and not args.dataset_id:
        ap.error("--dataset-id is required for B and C")
    args.out = args.out or os.path.join(RESULTS_DIR, f"llm_{args.config}.jsonl")
    run(args)


if __name__ == "__main__":
    main()
