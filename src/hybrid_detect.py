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
from utils import DetectionResult, merge_overlapping_spans, validate_aes_key

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


class HybridDetector:
    def __init__(self, ai_model_path: str = "models/pii_model_v2",
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

    def detect(self, text: str) -> List[DetectionResult]:
        results: List[DetectionResult] = []

        # --- Step 1: Presidio rule-based detection ---
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

        presidio_spans: set = set()
        for res in deduped:
            start, end = _trim_keyword_prefix(text, res.start, res.end, res.entity_type)
            results.append(DetectionResult(
                start=start, end=end,
                label=res.entity_type,
                text=text[start:end],
                source="PRESIDIO",
                score=res.score,
            ))
            presidio_spans.update(range(start, end))

        # --- Step 2: AI detection for spans Presidio missed ---
        if self.use_ai and self.ai_classifier:
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

            for ai_res in merged_ai:
                ai_start, ai_end, ai_score = ai_res["start"], ai_res["end"], ai_res["score"]
                if ai_score < self.ai_threshold:
                    continue
                if not any(i in presidio_spans for i in range(ai_start, ai_end)):
                    results.append(DetectionResult(
                        start=ai_start, end=ai_end,
                        label=ai_res["entity_group"],
                        text=text[ai_start:ai_end],
                        source="AI_MODEL",
                        score=ai_score,
                    ))

        results.sort(key=lambda x: x["start"])
        return results

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
    parser.add_argument("--model-path", type=str, default="models/pii_model_v2",
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
