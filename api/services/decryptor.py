"""
RBAC-aware token resolver.

For each [LABEL_hexid] token in a text chunk:
  - If user has a matching RbacGrant → decrypt from Redis and substitute
  - Otherwise → leave the token unchanged

Decryption uses the same Presidio AnonymizerEngine decrypt path used by the
existing decrypt_file.py to stay consistent.
"""
import base64
import re
import uuid
from typing import Set

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

_TOKEN_RE = re.compile(r"\[([A-Z_]{1,30})_([0-9a-f]{8})\]")

_anonymizer = AnonymizerEngine()


def _presidio_decrypt(encrypted_value: str, aes_key: bytes) -> str:
    key_b64 = base64.b64encode(aes_key).decode()
    fake = [RecognizerResult(entity_type="PII", start=0, end=len(encrypted_value), score=1.0)]
    result = _anonymizer.anonymize(
        text=encrypted_value,
        analyzer_results=fake,
        operators={"DEFAULT": OperatorConfig("decrypt", {"key": key_b64})},
    )
    return result.text


def resolve_tokens(
    text: str,
    token_map: dict[str, str],          # {token -> encrypted_value}  (session-level)
    aes_key: bytes,
    allowed_entity_types: Set[str],      # set of entity type strings; '*' means all
    dataset_token_map: dict[str, str] | None = None,  # ds:{dataset_id}:tokenmap entries
) -> str:
    """
    Replace tokens in *text* with their plaintext if the user has RBAC access.
    Checks session token_map first, then dataset_token_map.
    Tokens without RBAC access are left as-is.
    """
    if not text:
        return text

    allow_all = "*" in allowed_entity_types

    def _replace(match: re.Match) -> str:
        label, _ = match.group(1), match.group(2)
        token = match.group(0)

        if not (allow_all or label in allowed_entity_types):
            return token

        encrypted = token_map.get(token)
        if not encrypted and dataset_token_map:
            encrypted = dataset_token_map.get(token)
        if not encrypted:
            return token

        try:
            return _presidio_decrypt(encrypted, aes_key)
        except Exception:
            return token  # decryption failed — keep token, don't crash stream

    return _TOKEN_RE.sub(_replace, text)


async def get_allowed_entity_types(
    user_id: uuid.UUID,
    dataset_id: uuid.UUID | None,
    role: str,
    db,
) -> Set[str]:
    """
    Return the set of entity types this user may see in plaintext.

    Admin role always gets '*'. For other roles, query RbacGrant.
    """
    if role == "admin":
        return {"*"}

    if not dataset_id:
        return set()

    from sqlalchemy import select
    from api.models import RbacGrant

    result = await db.execute(
        select(RbacGrant.entity_type).where(
            RbacGrant.user_id == user_id,
            RbacGrant.dataset_id == dataset_id,
        )
    )
    return {row[0] for row in result}
