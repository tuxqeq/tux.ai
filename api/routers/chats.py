import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.models import ChatSession, Message, User

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
    messages = [
        MessageOut(
            id=str(m.id),
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs_result.scalars()
    ]
    return SessionDetail(
        id=str(session.id),
        title=session.title,
        dataset_id=str(session.dataset_id) if session.dataset_id else None,
        updated_at=session.updated_at.isoformat(),
        messages=messages,
    )


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
