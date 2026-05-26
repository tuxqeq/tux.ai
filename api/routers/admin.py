import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from api.models import Dataset, EncryptionKey, RbacGrant, User
from api.security import encrypt_aes_key, hash_password, key_ref
from api.services.redis_import import import_rdb

router = APIRouter(prefix="/api/admin", tags=["admin"])

_DATASET_NOT_FOUND = "Dataset not found"

# ── Users ──────────────────────────────────────────────────────────────────────

ANALYST_DEFAULT_GRANTS = ["PERSON", "EMAIL", "PHONE", "LOCATION", "ORG"]


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "viewer"


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return [UserOut(id=str(u.id), email=u.email, role=u.role, is_active=u.is_active)
            for u in result.scalars()]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="role must be admin, analyst, or viewer")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password), role=body.role)
    db.add(user)
    await db.flush()  # get user.id before committing

    # Auto-grant default entity types for analyst role
    if body.role == "analyst":
        datasets = await db.execute(select(Dataset))
        for dataset in datasets.scalars():
            for entity in ANALYST_DEFAULT_GRANTS:
                db.add(RbacGrant(
                    user_id=user.id,
                    dataset_id=dataset.id,
                    entity_type=entity,
                    granted_by=admin.id,
                ))

    await db.commit()
    return UserOut(id=str(user.id), email=user.email, role=user.role, is_active=user.is_active)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404)
    await db.delete(user)
    await db.commit()


# ── Datasets ───────────────────────────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str
    description: str | None = None


class DatasetOut(BaseModel):
    id: str
    name: str
    description: str | None
    has_key: bool
    model_name: str | None = None
    rdb_imported: bool = False


@router.get("/datasets", response_model=list[DatasetOut])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Dataset))
    datasets = result.scalars().all()
    keys_result = await db.execute(select(EncryptionKey.dataset_id))
    keyed = {row[0] for row in keys_result}
    return [DatasetOut(id=str(d.id), name=d.name, description=d.description,
                       has_key=d.id in keyed, model_name=d.model_name,
                       rdb_imported=d.rdb_imported) for d in datasets]


@router.post("/datasets", status_code=201, response_model=DatasetOut)
async def create_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    dataset = Dataset(name=body.name, description=body.description, created_by=admin.id)
    db.add(dataset)
    await db.commit()
    return DatasetOut(id=str(dataset.id), name=dataset.name,
                      description=dataset.description, has_key=False,
                      model_name=None, rdb_imported=False)


# ── Encryption Keys ────────────────────────────────────────────────────────────

class UploadKeyRequest(BaseModel):
    aes_key_hex: str  # hex-encoded AES key (32, 48, or 64 hex chars = 16/24/32 bytes)


@router.post("/datasets/{dataset_id}/key", status_code=201)
async def upload_key(
    dataset_id: uuid.UUID,
    body: UploadKeyRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        aes_key = bytes.fromhex(body.aes_key_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="aes_key_hex must be valid hex")
    if len(aes_key) not in (16, 24, 32):
        raise HTTPException(status_code=400, detail="Key must be 16, 24, or 32 bytes")

    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=_DATASET_NOT_FOUND)

    existing = await db.execute(
        select(EncryptionKey).where(EncryptionKey.dataset_id == dataset_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Key already set; delete it first")

    enc_key = EncryptionKey(
        dataset_id=dataset_id,
        encrypted_key=encrypt_aes_key(aes_key),
        key_ref=key_ref(aes_key),
        created_by=admin.id,
    )
    db.add(enc_key)
    await db.commit()
    return {"key_ref": enc_key.key_ref}


@router.delete("/datasets/{dataset_id}/key", status_code=204)
async def delete_key(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(EncryptionKey).where(EncryptionKey.dataset_id == dataset_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404)
    await db.delete(key)
    await db.commit()


# ── RBAC Grants ────────────────────────────────────────────────────────────────

class GrantRequest(BaseModel):
    user_id: uuid.UUID
    dataset_id: uuid.UUID
    entity_type: str  # e.g. 'EMAIL', 'SSN', '*' for all


@router.get("/rbac")
async def list_grants(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(RbacGrant))
    grants = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "user_id": str(g.user_id),
            "dataset_id": str(g.dataset_id),
            "entity_type": g.entity_type,
        }
        for g in grants
    ]


@router.post("/rbac", status_code=201)
async def add_grant(
    body: GrantRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await db.execute(
        select(RbacGrant).where(
            RbacGrant.user_id == body.user_id,
            RbacGrant.dataset_id == body.dataset_id,
            RbacGrant.entity_type == body.entity_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Grant already exists")
    grant = RbacGrant(
        user_id=body.user_id,
        dataset_id=body.dataset_id,
        entity_type=body.entity_type,
        granted_by=admin.id,
    )
    db.add(grant)
    await db.commit()
    return {"id": str(grant.id)}


@router.delete("/rbac/{grant_id}", status_code=204)
async def remove_grant(
    grant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(RbacGrant).where(RbacGrant.id == grant_id))
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=404)
    await db.delete(grant)
    await db.commit()


# ── Dataset: import dump.rdb ───────────────────────────────────────────────────

async def _do_rdb_import(dataset_id: uuid.UUID, rdb_bytes: bytes, dataset, db) -> dict:
    try:
        count = await import_rdb(dataset_id, rdb_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RDB import failed: {exc}")
    dataset.rdb_imported = True
    await db.commit()
    return {"imported_tokens": count}


@router.post("/datasets/{dataset_id}/import-rdb", status_code=200)
async def import_dataset_rdb(
    dataset_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=_DATASET_NOT_FOUND)
    if not file.filename or not file.filename.endswith(".rdb"):
        raise HTTPException(status_code=400, detail="File must be a .rdb file")
    rdb_bytes = await file.read()
    if not rdb_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return await _do_rdb_import(dataset_id, rdb_bytes, dataset, db)


class ImportRdbPathRequest(BaseModel):
    path: str  # absolute path on the server


@router.post("/datasets/{dataset_id}/import-rdb-path", status_code=200)
async def import_dataset_rdb_path(
    dataset_id: uuid.UUID,
    body: ImportRdbPathRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=_DATASET_NOT_FOUND)
    if not os.path.isfile(body.path):
        raise HTTPException(status_code=400, detail=f"File not found on server: {body.path}")
    rdb_bytes = await asyncio.get_event_loop().run_in_executor(None, _read_bytes, body.path)
    if not rdb_bytes:
        raise HTTPException(status_code=400, detail="File is empty")
    return await _do_rdb_import(dataset_id, rdb_bytes, dataset, db)


# ── Dataset: upload GGUF model ─────────────────────────────────────────────────

_GGUF_BASE = os.path.join(
    os.path.dirname(__file__), "..", "..", "llm", "uploads"
)


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def _write_text(path: str, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


@router.post("/datasets/{dataset_id}/upload-model", status_code=200)
async def upload_dataset_model(
    dataset_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=_DATASET_NOT_FOUND)

    fname = file.filename or ""
    if not fname.lower().endswith(_GGUF_EXT):
        raise HTTPException(status_code=400, detail="File must be a .gguf file")

    # Save to llm/uploads/{dataset_id}/model.gguf
    save_dir = os.path.join(_GGUF_BASE, str(dataset_id))
    os.makedirs(save_dir, exist_ok=True)
    gguf_path = os.path.join(save_dir, "model.gguf")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_bytes, gguf_path, data)

    # Derive a unique Ollama model name for this dataset
    safe_name = dataset.name.lower().replace(" ", "-")[:30]
    ollama_model = f"tux-ai-{safe_name}"

    # Write a Modelfile and register with Ollama
    modelfile_path = os.path.join(save_dir, "Modelfile")
    await loop.run_in_executor(None, _write_text, modelfile_path, f"FROM {gguf_path}\n")

    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "create", ollama_model, "-f", modelfile_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode()[:500])
    except asyncio.TimeoutError:
        raise HTTPException(status_code=500, detail="ollama create timed out (>5 min)")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ollama CLI not found on PATH")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"ollama create failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"unexpected error: {type(exc).__name__}: {exc}")

    dataset.model_name = ollama_model
    await db.commit()
    return {"model_name": ollama_model}


async def _register_gguf(gguf_path: str, dataset, db) -> dict:
    safe_name = dataset.name.lower().replace(" ", "-")[:30]
    ollama_model = f"tux-ai-{safe_name}"

    modelfile_path = gguf_path.replace(_GGUF_EXT, ".Modelfile")
    await asyncio.get_event_loop().run_in_executor(
        None, _write_text, modelfile_path, f"FROM {gguf_path}\n"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "create", ollama_model, "-f", modelfile_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode()[:500])
    except asyncio.TimeoutError:
        raise HTTPException(status_code=500, detail="ollama create timed out (>5 min)")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ollama CLI not found on PATH")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"ollama create failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"unexpected error: {type(exc).__name__}: {exc}")

    dataset.model_name = ollama_model
    await db.commit()
    return {"model_name": ollama_model}


class RegisterModelPathRequest(BaseModel):
    path: str  # absolute path to .gguf on the server


@router.post("/datasets/{dataset_id}/register-model-path", status_code=200)
async def register_model_path(
    dataset_id: uuid.UUID,
    body: RegisterModelPathRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=_DATASET_NOT_FOUND)
    if not os.path.isfile(body.path):
        raise HTTPException(status_code=400, detail=f"File not found on server: {body.path}")
    if not body.path.lower().endswith(_GGUF_EXT):
        raise HTTPException(status_code=400, detail="Path must point to a .gguf file")
    return await _register_gguf(body.path, dataset, db)
