import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from api.config import get_settings


# ── Passwords ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_ACCESS_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "access"},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh"},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ── CSRF ───────────────────────────────────────────────────────────────────────

def generate_csrf_token() -> str:
    return secrets.token_hex(32)


# ── Master-key encryption for stored AES keys ─────────────────────────────────

def _master_key_bytes() -> bytes:
    """Return the 32-byte master key from settings (UTF-8 encoded, zero-padded)."""
    raw = get_settings().MASTER_KEY.encode("utf-8")
    if len(raw) < 32:
        raw = raw.ljust(32, b"\x00")
    return raw[:32]


def encrypt_aes_key(aes_key: bytes) -> bytes:
    """Encrypt a dataset AES key with AES-256-GCM using the master key."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(_master_key_bytes())
    ciphertext = aesgcm.encrypt(nonce, aes_key, None)
    return nonce + ciphertext  # 12 bytes nonce + ciphertext+tag


def decrypt_aes_key(blob: bytes) -> bytes:
    """Decrypt a blob produced by encrypt_aes_key."""
    nonce, ciphertext = blob[:12], blob[12:]
    aesgcm = AESGCM(_master_key_bytes())
    return aesgcm.decrypt(nonce, ciphertext, None)


def key_ref(aes_key: bytes) -> str:
    """Short fingerprint of a key for audit purposes."""
    return hashlib.sha256(aes_key).hexdigest()[:12]
