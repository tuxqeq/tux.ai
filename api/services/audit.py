import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import AuditLog

_TOKEN_RE = re.compile(r"\[([A-Z_]{1,30})_([0-9a-f]{8})\]")


async def log_decryptions(
    original_text: str,
    resolved_text: str,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    """
    Log every token that was resolved (i.e. replaced with plaintext) in this chunk.
    A token was resolved if it appears in original_text but not in resolved_text.
    """
    original_tokens = set(_TOKEN_RE.findall(original_text))
    resolved_tokens = set(_TOKEN_RE.findall(resolved_text))
    decrypted = original_tokens - resolved_tokens

    if not decrypted:
        return

    for label, hexid in decrypted:
        db.add(AuditLog(
            user_id=user_id,
            entity_type=label,
            token=f"[{label}_{hexid}]",
            dataset_id=dataset_id,
            action="decrypt",
        ))
    await db.commit()
