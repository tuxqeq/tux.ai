"""
utils.py — Shared utilities for the tux.ai PII detection pipeline.
"""
from typing import Dict, List, Tuple

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


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
