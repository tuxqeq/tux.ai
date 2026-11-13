import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.deps import get_current_user, get_db
from api.models import ChatSession, EncryptionKey, Message, User
from api.security import decrypt_aes_key
from api.services.audit import log_decryptions
from api.services.decryptor import get_allowed_entity_types, resolve_tokens

router = APIRouter(prefix="/api/chats", tags=["chats"])


class SessionOut(BaseModel):
    id: str
    title: str | None
    dataset_id: str | None
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class SessionDetail(SessionOut):
    messages: list[MessageOut]


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
    )
    return [
        SessionOut(
            id=str(s.id),
            title=s.title,
            dataset_id=str(s.dataset_id) if s.dataset_id else None,
            updated_at=s.updated_at.isoformat(),
        )
        for s in result.scalars()
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404)

    msgs_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    stored = list(msgs_result.scalars())

    # Messages are stored tokenized. Resolve the tokens the user may see, as the live stream does,
    # and audit-log each decryption (D-29: history used to show bare type badges only).
    resolve = await _history_resolver(session, user, db)
    messages = []
    for m in stored:
        content = m.content
        if resolve is not None:
            content = resolve(m.content)
            if content != m.content:
                await log_decryptions(m.content, content, user.id, session.dataset_id, db)
        messages.append(MessageOut(
            id=str(m.id),
            role=m.role,
            content=content,
            created_at=m.created_at.isoformat(),
        ))
    return SessionDetail(
        id=str(session.id),
        title=session.title,
        dataset_id=str(session.dataset_id) if session.dataset_id else None,
        updated_at=session.updated_at.isoformat(),
        messages=messages,
    )


async def _history_resolver(session: ChatSession, user: User, db: AsyncSession):
    """str -> str that resolves the tokens of this session the user may see; None = nothing to do."""
    if not session.dataset_id:
        return None
    key_row = (await db.execute(
        select(EncryptionKey).where(EncryptionKey.dataset_id == session.dataset_id)
    )).scalar_one_or_none()
    if key_row is None:
        return None
    aes_key = decrypt_aes_key(key_row.encrypted_key)
    allowed = await get_allowed_entity_types(user.id, session.dataset_id, user.role, db)
    if not allowed:
        return None
    import redis as _redis
    r = _redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        session_map = r.hgetall(f"tokenmap:{session.id}") or {}
        dataset_map = r.hgetall(f"ds:{session.dataset_id}:tokenmap") or {}
    finally:
        r.close()
    return lambda text: resolve_tokens(text, session_map, aes_key, allowed, dataset_map)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404)
    await db.delete(session)
    await db.commit()
