import hashlib
import base64
import os
import sys
from typing import Dict, List, Tuple
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

sys.path.insert(0, os.path.dirname(__file__))
from utils import DetectionResult, merge_overlapping_spans, validate_aes_key

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
    "AWS_KEY":              "AWS_KEY",
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

    Token IDs are derived from an MD5 hash of the raw value, so the same
    value always maps to the same token across runs (reproducible datasets).

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
        self._token_map: Dict[str, str] = {}

    def _normalize_label(self, label: str) -> str:
        normalized = LABEL_NORM.get(label, label.upper())
        return normalized[:20]

    def _make_token(self, label: str, value: str) -> str:
        short_id = hashlib.md5(value.encode()).hexdigest()[:8]
        return f"[{self._normalize_label(label)}_{short_id}]"

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
                self._token_map[token] = self._encrypt_value(raw_value)
            token = self._value_to_token[raw_value]
            tokenized = tokenized[: span["start"]] + token + tokenized[span["end"]:]

        return tokenized, dict(self._token_map)

    def reset(self) -> None:
        """Clear accumulated state between independent files."""
        self._value_to_token.clear()
        self._token_map.clear()

    def get_token_map(self) -> Dict[str, str]:
        return dict(self._token_map)
