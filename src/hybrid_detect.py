import sys
import os
import argparse
from typing import List
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import re
import base64

os.environ["TOKENIZERS_PARALLELISM"] = "false"

sys.path.insert(0, os.path.dirname(__file__))
from recognizers import create_custom_recognizers
from utils import DetectionResult, PRESIDIO_TO_AI_LABEL, merge_overlapping_spans, validate_aes_key

# Entity types requested from Presidio on every detect() call
PRESIDIO_ENTITIES: List[str] = [
    # Built-in Presidio
    "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "CRYPTO",
    "IBAN_CODE", "IP_ADDRESS", "NRP",
    "LOCATION", "PERSON", "US_BANK_NUMBER", "US_DRIVER_LICENSE",
    "US_ITIN", "US_PASSPORT", "US_SSN", "UK_NHS",
    "MEDICAL_LICENSE", "URL",
    # Custom (from recognizers.py)
    "PROJECT_ID", "PASSPORT_NUMBER", "DRIVERS_LICENSE",
    "MEDICAL_RECORD_NUMBER", "BANK_ACCOUNT", "INSURANCE_NUMBER",
    "EMPLOYEE_ID", "DATE_OF_BIRTH", "TAX_ID", "VIN",
    "API_KEY", "USERNAME", "MAC_ADDRESS", "SECURITY_BADGE",
    "GRANT_NUMBER", "AWS_KEY", "SERVICE_API_KEY", "DB_CONNECTION",
    "LICENSE_PLATE", "PROFESSIONAL_LICENSE", "CVV", "MEDICARE_NUMBER",
    "PATENT_NUMBER",
]

# Labels whose with-label pattern captures the keyword word(s) before the value.
_KEYWORD_PREFIX_LABELS = {
    "VIN", "USERNAME", "API_KEY", "DATE_OF_BIRTH",
    "INSURANCE_NUMBER", "GRANT_NUMBER",
}


def _trim_keyword_prefix(text: str, start: int, end: int, label: str):
    """Strip leading keyword word(s) captured by with-label patterns."""
    if label not in _KEYWORD_PREFIX_LABELS:
        return start, end
    span = text[start:end]
    for sep in (" ", ":", "-"):
        idx = span.rfind(sep)
        if idx != -1:
            new_start = start + idx + 1
            if new_start < end:
                return new_start, end
    return start, end


_WORD_RE = re.compile(r"\S+")
_TRIM_LEFT = "([{\"'"
_TRIM_RIGHT = ".,;:!?)]}\"'"


def words_to_spans(text: str, word_spans, labels, scores, threshold: float) -> List[DetectionResult]:
    """Build entity spans from per-word BIO labels (word-level inference, as in training).

    word_spans: [(start, end)] of whitespace-delimited words; labels: "O" | "B-X" | "I-X" per word;
    scores: probability of each word's label. A span's score is the mean of its words' scores.
    Leading/trailing punctuation is trimmed from each span.
    """
    results: List[DetectionResult] = []
    cur = None  # [start, end, label, [scores]]

    def close():
        if cur is None:
            return
        s, e = cur[0], cur[1]
        while s < e and text[s] in _TRIM_LEFT:
            s += 1
        while e > s and text[e - 1] in _TRIM_RIGHT:
            e -= 1
        score = sum(cur[3]) / len(cur[3])
        if e > s and score >= threshold:
            results.append(DetectionResult(start=s, end=e, label=cur[2], text=text[s:e],
                                           source="AI_MODEL", score=score))

    for (ws, we), lab, sc in zip(word_spans, labels, scores):
        if lab == "O":
            close()
            cur = None
            continue
        prefix, ent = lab.split("-", 1)
        if cur is not None and prefix == "I" and ent == cur[2]:
            cur[1] = we
            cur[3].append(sc)
        else:
            close()
            cur = [ws, we, ent, [sc]]
    close()
    return results


def _tie_priority(r: DetectionResult) -> int:
    """Label priority when spans have the same length (see HybridDetector.combine_union)."""
    if r["source"] == "AI_MODEL":
        return 1
    return 0 if r["label"] in PRESIDIO_TO_AI_LABEL else 2


class HybridDetector:
    def __init__(self, ai_model_path: str = "models/pii_model_v3",
                 use_ai: bool = True, ai_threshold: float = 0.95):
        if not (0.0 <= ai_threshold <= 1.0):
            raise ValueError(f"ai_threshold must be between 0 and 1, got {ai_threshold}")

        print("Initializing Hybrid Detector (AI + `Presidio`)...")
        self.use_ai = use_ai
        self.ai_threshold = ai_threshold

        print("Loading `Presidio` analyzer...")
        self.analyzer = AnalyzerEngine()
        for recognizer in create_custom_recognizers():
            self.analyzer.registry.add_recognizer(recognizer)

        if self.use_ai:
            if not os.path.exists(ai_model_path):
                raise FileNotFoundError(f"AI model not found: {ai_model_path}")
            weights = ("model.safetensors", "pytorch_model.bin")
            if not any(os.path.exists(os.path.join(ai_model_path, w)) for w in weights):
                raise FileNotFoundError(
                    f"No model weights in {ai_model_path} (expected model.safetensors). "
                    "Train them with: bash scripts/retrain_detector.sh, or run with --no-ai."
                )
            from transformers import pipeline
            print(f"Loading AI model from {ai_model_path}...")
            self.ai_classifier = pipeline(
                "token-classification",
                model=ai_model_path,
                tokenizer=ai_model_path,
                aggregation_strategy="simple",
            )
            print(f"AI threshold set to: {ai_threshold} (only high-confidence detections)")
        else:
            print("AI detection disabled - using Presidio rules only")
            self.ai_classifier = None

        print("Hybrid detector ready!")

    def detect_presidio(self, text: str) -> List[DetectionResult]:
        """Step 1: Presidio rule-based detection, overlapping spans deduplicated."""
        presidio_results = self.analyzer.analyze(
            text=text,
            entities=PRESIDIO_ENTITIES,
            language="en",
        )

        # Deduplicate overlapping Presidio spans, keeping highest score
        sorted_pres = sorted(presidio_results, key=lambda r: (r.start, -r.score))
        deduped = []
        for res in sorted_pres:
            overlaps = any(
                max(res.start, kept.start) < min(res.end, kept.end)
                for kept in deduped
            )
            if not overlaps:
                deduped.append(res)
            else:
                for i, kept in enumerate(deduped):
                    if max(res.start, kept.start) < min(res.end, kept.end):
                        if res.score > kept.score:
                            deduped[i] = res
                        break

        results: List[DetectionResult] = []
        for res in deduped:
            start, end = _trim_keyword_prefix(text, res.start, res.end, res.entity_type)
            results.append(DetectionResult(
                start=start, end=end,
                label=res.entity_type,
                text=text[start:end],
                source="PRESIDIO",
                score=res.score,
            ))
        return results

    def detect_ai(self, text: str, granularity: str = "subtoken") -> List[DetectionResult]:
        """Step 2: AI token classification above ai_threshold, without the Presidio filter.

        granularity="word" (production): one label per whitespace word from its first sub-token,
        which is how the model was trained (src/train.py labels only first sub-tokens).
        granularity="subtoken" (old): HF pipeline, aggregation over all sub-tokens; it splits
        entities such as SSNs and API keys into fragments.
        """
        if not (self.use_ai and self.ai_classifier):
            return []
        if granularity == "word":
            return self._ai_word_level(text)
        raw_ai = self.ai_classifier(text)

        # Merge consecutive sub-token fragments of the same entity
        merged_ai = []
        for ai_res in raw_ai:
            if (merged_ai
                    and merged_ai[-1]["entity_group"] == ai_res["entity_group"]
                    and ai_res["start"] <= merged_ai[-1]["end"] + 1):
                merged_ai[-1]["end"] = ai_res["end"]
                merged_ai[-1]["score"] = max(merged_ai[-1]["score"], ai_res["score"])
            else:
                merged_ai.append(dict(ai_res))

        results: List[DetectionResult] = []
        for ai_res in merged_ai:
            ai_start, ai_end, ai_score = ai_res["start"], ai_res["end"], ai_res["score"]
            if ai_score < self.ai_threshold:
                continue
            results.append(DetectionResult(
                start=ai_start, end=ai_end,
                label=ai_res["entity_group"],
                text=text[ai_start:ai_end],
                source="AI_MODEL",
                score=ai_score,
            ))
        return results

    def _ai_word_level(self, text: str) -> List[DetectionResult]:
        import torch
        word_spans = [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]
        if not word_spans:
            return []
        tok, model = self.ai_classifier.tokenizer, self.ai_classifier.model
        enc = tok([text[s:e] for s, e in word_spans], is_split_into_words=True,
                  truncation=True, max_length=512, return_tensors="pt")
        word_ids = enc.word_ids(0)
        with torch.no_grad():
            logits = model(**{k: v.to(model.device) for k, v in enc.items()}).logits[0]
        probs = torch.softmax(logits, dim=-1).cpu()
        labels = ["O"] * len(word_spans)
        scores = [1.0] * len(word_spans)
        seen = set()
        for pos, wid in enumerate(word_ids):
            if wid is None or wid in seen:
                continue
            seen.add(wid)
            p, idx = probs[pos].max(dim=-1)
            labels[wid] = model.config.id2label[int(idx)]
            scores[wid] = float(p)
        return words_to_spans(text, word_spans, labels, scores, self.ai_threshold)

    @staticmethod
    def combine_union(presidio_results: List[DetectionResult],
                      ai_results: List[DetectionResult], text: str) -> List[DetectionResult]:
        """Production hybrid rule (since 2026-11-07): union of both layers. Overlapping spans merge
        into one span that covers all of them; its label comes from the longest member.
        Tie on length: a Presidio label the AI model cannot predict (AWS_KEY, IBAN_CODE, ...) wins,
        because it is more specific; otherwise the AI label wins.

        Chosen on eval/eval_detector.py results: vs. the old rule (combine), leaked PII characters
        on held-out templates fell from 8.9% to 0.06% and typed F1 rose from 0.910 to 0.994.
        """
        spans = sorted(list(presidio_results) + list(ai_results), key=lambda r: (r["start"], -r["end"]))
        groups = []
        for r in spans:
            if groups and r["start"] < groups[-1]["end"]:
                groups[-1]["end"] = max(groups[-1]["end"], r["end"])
                groups[-1]["members"].append(r)
            else:
                groups.append({"start": r["start"], "end": r["end"], "members": [r]})
        results: List[DetectionResult] = []
        for g in groups:
            best = max(g["members"], key=lambda r: (r["end"] - r["start"], _tie_priority(r)))
            results.append(DetectionResult(start=g["start"], end=g["end"], label=best["label"],
                                           text=text[g["start"]:g["end"]], source=best["source"],
                                           score=best["score"]))
        return results

    @staticmethod
    def combine(presidio_results: List[DetectionResult],
                ai_results: List[DetectionResult]) -> List[DetectionResult]:
        """Old hybrid rule (until 2026-11-07), kept for evaluation: keep every Presidio span; add an
        AI span only where Presidio found nothing. Leaks the rest of an entity when Presidio
        covers only part of it."""
        presidio_spans: set = set()
        for r in presidio_results:
            presidio_spans.update(range(r["start"], r["end"]))
        results = list(presidio_results)
        for r in ai_results:
            if not any(i in presidio_spans for i in range(r["start"], r["end"])):
                results.append(r)
        results.sort(key=lambda x: x["start"])
        return results

    def detect(self, text: str) -> List[DetectionResult]:
        """Presidio + word-level AI, merged with combine_union."""
        return self.combine_union(self.detect_presidio(text),
                                  self.detect_ai(text, granularity="word"), text)

    def encrypt_text(self, text: str, results: List[DetectionResult], aes_key: bytes) -> str:
        """Encrypt detected PII spans in text using AES (reversible)."""
        validate_aes_key(aes_key)
        if not results:
            return text

        merged = merge_overlapping_spans(results, text)

        presidio_results = [
            RecognizerResult(
                entity_type=r["label"],
                start=r["start"],
                end=r["end"],
                score=r["score"],
            )
            for r in merged
        ]

        anonymizer = AnonymizerEngine()
        key_b64 = base64.b64encode(aes_key).decode("utf-8")
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=presidio_results,
            operators={"DEFAULT": OperatorConfig("encrypt", {"key": key_b64})},
        )
        return anonymized.text


def _print_results(results: List[DetectionResult]) -> None:
    print(f"\nFound {len(results)} entities:")
    for r in results:
        print(f"  [{r['source']}] {r['label']}: '{r['text']}' (Score: {r['score']:.2f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid PII Detection and Encryption")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", type=str, help="Text to analyze")
    group.add_argument("--file", type=str, help="File to analyze")
    parser.add_argument("--output", type=str, help="Output file for encrypted text")
    parser.add_argument("--model-path", type=str, default="models/pii_model_v3",
                        help="Path to AI model")
    parser.add_argument("--encrypt", action="store_true", help="Encrypt detected PII")
    parser.add_argument("--key", type=str, default="16ByteSecureKey!",
                        help="AES key (16/24/32 bytes)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Disable AI; use Presidio rules only")
    parser.add_argument("--ai-threshold", type=float, default=0.95,
                        help="Min AI confidence (0.0–1.0, default: 0.95)")
    args = parser.parse_args()

    aes_key = args.key.encode("utf-8")
    try:
        validate_aes_key(aes_key)
    except ValueError as e:
        print(f"ERROR: {e}")
        return

    detector = HybridDetector(
        ai_model_path=args.model_path,
        use_ai=not args.no_ai,
        ai_threshold=args.ai_threshold,
    )

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        print("Enter text to analyze (type 'exit' to quit):")
        while True:
            text = input(">> ")
            if text.lower() in ("exit", "quit"):
                break
            _print_results(detector.detect(text))
        return

    results = detector.detect(text)
    _print_results(results)

    if args.encrypt and results:
        encrypted = detector.encrypt_text(text, results, aes_key)
        print(f"\n{'='*70}\nENCRYPTED TEXT:\n{'='*70}\n{encrypted}\n{'='*70}\n")
        out_path = args.output or (
            args.file.replace(".txt", "_encrypted.txt") if args.file else None
        )
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(encrypted)
            print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
