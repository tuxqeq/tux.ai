"""
redis_client.py — Production-ready Redis client for tux.ai token map storage.

Features:
- Connection pooling (one pool per URL, reused across calls)
- Auth + TLS support via REDIS_URL environment variable
- Session index: filemap:{filename} -> session_id for lookup by filename
- Key reference metadata stored alongside each token map
- Atomic write with rollback support
"""

import os
import threading
import time
from typing import Dict

import redis

DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DEFAULT_TTL       = 60 * 60 * 24 * 30  # 30 days

_pools: Dict[str, redis.ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(url: str) -> redis.ConnectionPool:
    with _pools_lock:
        if url not in _pools:
            _pools[url] = redis.ConnectionPool.from_url(
                url,
                decode_responses=True,
                max_connections=10,
                socket_connect_timeout=5,
                socket_timeout=10,
            )
        return _pools[url]


def get_client(url: str) -> redis.Redis:
    return redis.Redis(connection_pool=get_pool(url))


def store_token_map(
    token_map: Dict[str, str],
    session_id: str,
    filename: str,
    key_id: str,
    url: str = DEFAULT_REDIS_URL,
    ttl: int = DEFAULT_TTL,
) -> None:
    """
    Atomically store a token map in Redis with full metadata.

    Keys written:
      tokenmap:{session_id}  — hash of { token -> AES-encrypted value }
      filemap:{filename}     — session_id (lookup by filename)
      keyref:{session_id}    — metadata hash (filename, key_id, timestamp, token_count)

    Raises redis.RedisError on failure — caller is responsible for rollback.
    """
    if not token_map:
        return

    r = get_client(url)
    pipe = r.pipeline(transaction=True)

    pipe.hset(f"tokenmap:{session_id}", mapping=token_map)
    pipe.expire(f"tokenmap:{session_id}", ttl)

    pipe.set(f"filemap:{filename}", session_id, ex=ttl)

    pipe.hset(f"keyref:{session_id}", mapping={
        "filename":    filename,
        "key_id":      key_id,
        "timestamp":   str(int(time.time())),
        "token_count": str(len(token_map)),
    })
    pipe.expire(f"keyref:{session_id}", ttl)

    pipe.execute()


def get_session_id(filename: str, url: str = DEFAULT_REDIS_URL) -> str | None:
    """Look up the session ID for a previously tokenized filename."""
    return get_client(url).get(f"filemap:{filename}")


def get_token_map(session_id: str, url: str = DEFAULT_REDIS_URL) -> Dict[str, str]:
    """Retrieve the full token map for a session."""
    return get_client(url).hgetall(f"tokenmap:{session_id}")


def get_token(session_id: str, token: str, url: str = DEFAULT_REDIS_URL) -> str | None:
    """Look up a single token's encrypted value."""
    return get_client(url).hget(f"tokenmap:{session_id}", token)


def get_session_meta(session_id: str, url: str = DEFAULT_REDIS_URL) -> Dict[str, str]:
    """Retrieve metadata for a session (filename, key_id, timestamp, token_count)."""
    return get_client(url).hgetall(f"keyref:{session_id}")


def ping(url: str = DEFAULT_REDIS_URL) -> bool:
    try:
        return get_client(url).ping()
    except Exception:
        return False
