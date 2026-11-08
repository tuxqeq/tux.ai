import hashlib
import hmac
import base64
import logging
import os
import sys
from typing import Dict, List, Tuple
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

sys.path.insert(0, os.path.dirname(__file__))
from utils import DetectionResult, merge_overlapping_spans, validate_aes_key

log = logging.getLogger("tuxai")

# Token id = first TOKEN_ID_HEX hex chars of HMAC-SHA256(subkey, value); subkey derived from the
# dataset AES key. Same value + same key -> same token (needed to match query tokens with corpus
# tokens in RAG), but without the key a token cannot be checked against guessed values.
# 12 hex = 48 bits: with 100k distinct values the chance of any collision is about 2e-5.
# (Until 2026-11-08 the id was md5(value)[:8]: unkeyed, so SSNs/DOBs/names could be brute-forced
# from the token alone, and 32 bits gave a real collision risk on a 60k-value corpus.)
TOKEN_ID_HEX = 12
_TOKEN_ID_CONTEXT = b"tux.ai/token-id/v2"


def token_id(aes_key: bytes, value: str, length: int = TOKEN_ID_HEX) -> str:
    subkey = hmac.new(aes_key, _TOKEN_ID_CONTEXT, hashlib.sha256).digest()
    return hmac.new(subkey, value.encode("utf-8"), hashlib.sha256).hexdigest()[:length]


# Normalize Presidio / AI model labels to short, readable token names
LABEL_NORM: Dict[str, str] = {
    # Presidio built-ins
    "PERSON":               "PERSON",
    "EMAIL_ADDRESS":        "EMAIL",
    "PHONE_NUMBER":         "PHONE",
    "CREDIT_CARD":          "CREDIT_CARD",
    "LOCATION":             "LOCATION",
    "IP_ADDRESS":           "IP",
    "US_SSN":               "SSN",
    "IBAN_CODE":            "IBAN",
    "URL":                  "URL",
    "NRP":                  "NRP",
    "US_BANK_NUMBER":       "BANK",
    "US_ITIN":              "ITIN",
    "US_DRIVER_LICENSE":    "DL",
    "US_PASSPORT":          "PASSPORT",
    "CRYPTO":               "CRYPTO",
    "UK_NHS":               "NHS",
    "MEDICAL_LICENSE":      "MEDICAL_LICENSE",
    # AI model labels
    "PER":                  "PERSON",
    "ORG":                  "ORG",
    "LOC":                  "LOCATION",
    "LICENSE":              "DL",
    "MISC":                 "MISC",
    # Generic fallback used by generate_data.py
    "PII":                  "PII",
    # Custom recognizers
    "PROJECT_ID":           "PROJECT_ID",
    "PASSPORT_NUMBER":      "PASSPORT",
    "DRIVERS_LICENSE":      "DL",
    "MEDICAL_RECORD_NUMBER": "MRN",
    "BANK_ACCOUNT":         "BANK",
    "INSURANCE_NUMBER":     "INSURANCE",
    "EMPLOYEE_ID":          "EMP_ID",
    "DATE_OF_BIRTH":        "DOB",
    "TAX_ID":               "TAX_ID",
    "VIN":                  "VIN",
    "API_KEY":              "API_KEY",
    "USERNAME":             "USERNAME",
    "MAC_ADDRESS":          "MAC",
    "SECURITY_BADGE":       "BADGE",
    "GRANT_NUMBER":         "GRANT",
    "AWS_KEY":              "API_KEY",   # one key type: the AI layer labels AWS keys API_KEY
    "SERVICE_API_KEY":      "API_KEY",
    "DB_CONNECTION":        "DB_CONN",
    "LICENSE_PLATE":        "PLATE",
    "PROFESSIONAL_LICENSE": "PROF_LICENSE",
    "CVV":                  "CVV",
    "MEDICARE_NUMBER":      "MEDICARE",
    "PATENT_NUMBER":        "PATENT",
}


class PIIPseudonymizer:
    """
    Replaces detected PII spans with readable tokens like [PERSON_a1b2c3d4]
    and maintains a map of { token -> AES-encrypted original value }.

    Token IDs are a keyed hash (HMAC-SHA256) of the raw value, so the same value always maps
    to the same token under the same key (reproducible datasets, RAG lookups), and a token
    cannot be reversed by guessing values without the key.

    Usage:
        p = PIIPseudonymizer(b"16ByteSecureKey!")
        tokenized, token_map = p.pseudonymize(text, detector.detect(text))
    """

    def __init__(self, aes_key: bytes) -> None:
        validate_aes_key(aes_key)
        self._aes_key = aes_key
        self._key_b64 = base64.b64encode(aes_key).decode("utf-8")
        self._anonymizer = AnonymizerEngine()
        self._value_to_token: Dict[str, str] = {}
        self._token_to_value: Dict[str, str] = {}
        self._token_map: Dict[str, str] = {}

    def _normalize_label(self, label: str) -> str:
        normalized = LABEL_NORM.get(label, label.upper())
        return normalized[:20]

    def _make_token(self, label: str, value: str) -> str:
        token = f"[{self._normalize_label(label)}_{token_id(self._aes_key, value)}]"
        if self._token_to_value.get(token, value) != value:
            # 48-bit collision with a different value: use the longer id for this value
            log.warning("token id collision; using a 16-hex id")
            token = f"[{self._normalize_label(label)}_{token_id(self._aes_key, value, 16)}]"
        return token

    def _encrypt_value(self, value: str) -> str:
        fake_result = [RecognizerResult(entity_type="PII", start=0, end=len(value), score=1.0)]
        op_config = {"DEFAULT": OperatorConfig("encrypt", {"key": self._key_b64})}
        result = self._anonymizer.anonymize(
            text=value, analyzer_results=fake_result, operators=op_config
        )
        return result.text

    def pseudonymize(
        self, text: str, detections: List[DetectionResult]
    ) -> Tuple[str, Dict[str, str]]:
        """
        Replace each detected PII span with a token and record the AES-encrypted
        original in the token map.

        Returns:
            (tokenized_text, token_map_snapshot)
        """
        if not detections:
            return text, dict(self._token_map)

        merged = merge_overlapping_spans(detections, text)

        tokenized = text
        for span in reversed(merged):
            raw_value = tokenized[span["start"]:span["end"]]
            if raw_value not in self._value_to_token:
                token = self._make_token(span["label"], raw_value)
                self._value_to_token[raw_value] = token
                self._token_to_value[token] = raw_value
                self._token_map[token] = self._encrypt_value(raw_value)
            token = self._value_to_token[raw_value]
            tokenized = tokenized[: span["start"]] + token + tokenized[span["end"]:]

        return tokenized, dict(self._token_map)

    def reset(self) -> None:
        """Clear accumulated state between independent files."""
        self._value_to_token.clear()
        self._token_to_value.clear()
        self._token_map.clear()

    def get_token_map(self) -> Dict[str, str]:
        return dict(self._token_map)

    def get_plaintext_map(self) -> Dict[str, str]:
        """Return {token: original_plaintext} — useful for exporting the recovery map."""
        return {token: value for value, token in self._value_to_token.items()}
