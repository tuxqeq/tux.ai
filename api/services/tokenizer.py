"""
Wraps PIIPseudonymizer + HybridDetector for the API layer.

Sanitizes input first (strips characters that could spoof token syntax),
then tokenizes detected PII using the dataset AES key.
"""
import re
import sys
import os
from typing import Tuple, Dict

# Ensure src/ is on the path so we can import the existing detection code
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.pseudonymize import PIIPseudonymizer
from src.hybrid_detect import HybridDetector

_MODEL_FALLBACKS = [
    "models/pii_model_advanced",
    "models/pii_model_large",
    "models/pii_model_v2",
    "models/pii_model",
]

# Shared detector instance (model loaded once per process)
_detector: HybridDetector | None = None


def _resolve_model_path(requested: str) -> tuple[str, bool]:
    """Return (path, use_ai). Falls back to Presidio-only if no model found."""
    candidates = [requested] + [p for p in _MODEL_FALLBACKS if p != requested]
    for candidate in candidates:
        full = os.path.join(_ROOT, candidate)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "model.safetensors")):
            return candidate, True
    return requested, False  # Presidio-only fallback


def get_detector(model_path: str) -> HybridDetector:
    global _detector
    if _detector is None:
        resolved_path, use_ai = _resolve_model_path(model_path)
        _detector = HybridDetector(model_path=resolved_path, use_ai=use_ai)
    return _detector


# Characters that could inject fake tokens into the pipeline
_INJECTION_RE = re.compile(r"[\[\]\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_input(text: str) -> str:
    """Strip characters that could forge [LABEL_hex] tokens or contain control chars."""
    return _INJECTION_RE.sub("", text).strip()


def tokenize_message(
    text: str,
    aes_key: bytes,
    model_path: str,
) -> Tuple[str, Dict[str, str]]:
    """
    Detect PII in *text* and replace with [LABEL_hexid] tokens.

    Returns:
        (tokenized_text, token_map)  where token_map is {token: encrypted_value}
    """
    sanitized = sanitize_input(text)
    detector = get_detector(model_path)
    detections = detector.detect(sanitized)

    pseudonymizer = PIIPseudonymizer(aes_key)
    tokenized, token_map = pseudonymizer.pseudonymize(sanitized, detections)
    return tokenized, token_map
