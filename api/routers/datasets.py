"""
Datasets a signed-in user can chat with (D-29). The admin list (/api/admin/datasets) needs the admin
role; the chat page needs a plain list for every role. Only datasets with a key are listed: a chat
without a key cannot tokenize, and the chat service refuses it.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.models import Dataset, EncryptionKey, User

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class ChatDatasetOut(BaseModel):
    id: str
    name: str
    description: str | None


@router.get("", response_model=list[ChatDatasetOut])
async def list_chat_datasets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).join(EncryptionKey, EncryptionKey.dataset_id == Dataset.id).order_by(Dataset.created_at)
    )
    return [ChatDatasetOut(id=str(d.id), name=d.name, description=d.description) for d in result.scalars()]
