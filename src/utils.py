"""
utils.py — Shared utilities for the tux.ai PII detection pipeline.
"""
from typing import Dict, List, Tuple

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


# Presidio label -> the AI model label for the same kind of PII. Presidio labels that are NOT
# here (AWS_KEY, IBAN_CODE, TAX_ID, CVV, ...) are more specific than anything the model predicts.
PRESIDIO_TO_AI_LABEL: Dict[str, str] = {
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
    "MAC_ADDRESS": "MAC",
    "EMPLOYEE_ID": "EMP_ID",
    "INSURANCE_NUMBER": "INSURANCE",
}


class DetectionResult(TypedDict):
    start: int
    end: int
    label: str
    text: str
    source: str   # "PRESIDIO" | "AI_MODEL"
    score: float


def merge_overlapping_spans(spans: List[DetectionResult], text: str) -> List[DetectionResult]:
    """
    Sort spans by start position, then merge any overlapping or adjacent spans.
    When two spans overlap the one with the higher score wins the label/source.
    Returns a new list; does not mutate the input.
    """
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda x: x["start"])
    merged: List[DetectionResult] = []
    current: DetectionResult = dict(sorted_spans[0])  # type: ignore[assignment]

    for nxt in sorted_spans[1:]:
        if nxt["start"] <= current["end"] + 1:
            current["end"] = max(current["end"], nxt["end"])
            current["text"] = text[current["start"]:current["end"]]
            if nxt["score"] > current["score"]:
                current["label"] = nxt["label"]
                current["source"] = nxt["source"]
                current["score"] = nxt["score"]
        else:
            merged.append(current)
            current = dict(nxt)  # type: ignore[assignment]

    merged.append(current)
    return merged


def validate_aes_key(key: bytes) -> None:
    """Raise ValueError if key length is not 16, 24, or 32 bytes."""
    if len(key) not in (16, 24, 32):
        raise ValueError(
            f"AES key must be 16, 24, or 32 bytes; got {len(key)}"
        )
