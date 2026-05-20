"""
Import a dump.rdb token map into Redis under ds:{dataset_id}:tokenmap.

Strategy:
  1. Write the uploaded .rdb to a temp file
  2. Start a disposable redis:latest container with the rdb mounted as /data/dump.rdb
  3. HGETALL tokenmap:* keys from that container using redis-cli
  4. HSET each entry into ds:{dataset_id}:tokenmap in the main Redis
  5. Stop + remove the temp container
"""
import asyncio
import os
import subprocess
import tempfile
import uuid

import redis.asyncio as aioredis

from api.config import get_settings

_TEMP_PORT = 16379  # port for the temp container; unlikely to collide


async def import_rdb(dataset_id: uuid.UUID, rdb_bytes: bytes) -> int:
    """
    Load *rdb_bytes* into Redis and merge all tokenmap:* entries into
    ds:{dataset_id}:tokenmap.  Returns the number of token entries imported.
    """
    settings = get_settings()
    container_name = f"tuxai-rdb-import-{dataset_id.hex[:8]}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        rdb_path = os.path.join(tmp_dir, "dump.rdb")
        with open(rdb_path, "wb") as f:
            f.write(rdb_bytes)

        # Start temp Redis container
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "-p", f"{_TEMP_PORT}:6379",
                "-v", f"{rdb_path}:/data/dump.rdb:ro",
                "redis:latest",
                "redis-server", "--save", "", "--appendonly", "no",
                "--dir", "/data",
                "--dbfilename", "dump.rdb",
            ],
            check=True,
            capture_output=True,
        )

        try:
            # Wait until Redis is ready
            for _ in range(20):
                try:
                    result = subprocess.run(
                        ["docker", "exec", container_name, "redis-cli", "ping"],
                        capture_output=True, text=True, timeout=2,
                    )
                    if result.stdout.strip() == "PONG":
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            # Read all keys matching tokenmap:*
            keys_result = subprocess.run(
                ["docker", "exec", container_name, "redis-cli", "keys", "tokenmap:*"],
                capture_output=True, text=True, check=True,
            )
            keys = [k.strip() for k in keys_result.stdout.splitlines() if k.strip()]

            if not keys:
                return 0

            # For each key, dump all hash fields
            all_entries: dict[str, str] = {}
            for key in keys:
                hgetall = subprocess.run(
                    ["docker", "exec", container_name, "redis-cli", "hgetall", key],
                    capture_output=True, text=True, check=True,
                )
                lines = [l.strip() for l in hgetall.stdout.splitlines() if l.strip()]
                # redis-cli hgetall prints alternating field / value lines
                for i in range(0, len(lines) - 1, 2):
                    all_entries[lines[i]] = lines[i + 1]

        finally:
            subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
            )

    if not all_entries:
        return 0

    # Write into main Redis
    target_key = f"ds:{dataset_id}:tokenmap"
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with r.pipeline() as pipe:
            pipe.hset(target_key, mapping=all_entries)
            await pipe.execute()
    finally:
        await r.aclose()

    return len(all_entries)
