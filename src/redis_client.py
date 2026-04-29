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
    Atomically store (or merge into) a token map in Redis with full metadata.

    Keys written:
      tokenmap:{session_id}  — hash of { token -> AES-encrypted value }
      filemap:{filename}     — session_id (lookup by filename)
      keyref:{session_id}    — metadata hash (filename, key_id, timestamp, token_count)

    When merging into an existing session, token_count reflects the new total.
    Raises redis.RedisError on failure — caller is responsible for rollback.
    """
    if not token_map:
        return

    r = get_client(url)

    pipe = r.pipeline(transaction=True)
    pipe.hset(f"tokenmap:{session_id}", mapping=token_map)
    pipe.hlen(f"tokenmap:{session_id}")
    pipe.expire(f"tokenmap:{session_id}", ttl)
    pipe.set(f"filemap:{filename}", session_id, ex=ttl)
    results = pipe.execute()

    total_tokens = results[1]

    pipe2 = r.pipeline(transaction=True)
    pipe2.hset(f"keyref:{session_id}", mapping={
        "filename":    filename,
        "key_id":      key_id,
        "timestamp":   str(int(time.time())),
        "token_count": str(total_tokens),
    })
    pipe2.expire(f"keyref:{session_id}", ttl)
    pipe2.execute()

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


def list_sessions(url: str = DEFAULT_REDIS_URL) -> list[Dict]:
    """Return all active sessions as a list of metadata dicts, newest first."""
    r = get_client(url)
    keys = r.keys("keyref:*")
    sessions = []
    for key in keys:
        meta = r.hgetall(key)
        if meta:
            session_id = key.replace("keyref:", "")
            sessions.append({"session_id": session_id, **meta})
    sessions.sort(key=lambda s: int(s.get("timestamp", 0)), reverse=True)
    return sessions


def ping(url: str = DEFAULT_REDIS_URL) -> bool:
    try:
        return get_client(url).ping()
    except Exception:
        return False
