"""
Import a dump.rdb token map into Redis under ds:{dataset_id}:tokenmap.

Strategy (Docker available):
  1. Start a disposable redis:latest container with the rdb mounted
  2. HGETALL tokenmap:* keys from that container
  3. HSET entries into ds:{dataset_id}:tokenmap in main Redis
  4. Stop the container

Strategy (no Docker — native fallback):
  1. Start a native redis-server on a temp port pointing at the rdb file
  2. Read tokenmap:* keys via redis-cli
  3. HSET into main Redis
  4. Stop the temp server
"""
import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import uuid

import redis.asyncio as aioredis

from api.config import get_settings

_TEMP_PORT = 16379


def _docker_available() -> bool:
    return (
        os.path.exists("/var/run/docker.sock")
        and shutil.which("docker") is not None
        and subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    )


async def import_rdb(dataset_id: uuid.UUID, rdb_bytes: bytes) -> int:
    settings = get_settings()

    with tempfile.TemporaryDirectory() as tmp_dir:
        rdb_path = os.path.join(tmp_dir, "dump.rdb")
        with open(rdb_path, "wb") as f:
            f.write(rdb_bytes)

        if _docker_available():
            all_entries = await _import_via_docker(tmp_dir, rdb_path, dataset_id)
        else:
            all_entries = await _import_via_native(tmp_dir, rdb_path)

    if not all_entries:
        return 0

    target_key = f"ds:{dataset_id}:tokenmap"
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        async with r.pipeline() as pipe:
            pipe.hset(target_key, mapping=all_entries)
            await pipe.execute()
    finally:
        await r.aclose()

    return len(all_entries)


async def _import_via_docker(tmp_dir: str, rdb_path: str, dataset_id: uuid.UUID) -> dict[str, str]:
    container_name = f"tuxai-rdb-import-{dataset_id.hex[:8]}"
    subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "--name", container_name,
            "-p", f"{_TEMP_PORT}:6379",
            "-v", f"{rdb_path}:/data/dump.rdb:ro",
            "redis:latest",
            "redis-server", "--save", "", "--appendonly", "no",
            "--dir", "/data", "--dbfilename", "dump.rdb",
        ],
        check=True, capture_output=True,
    )
    try:
        for _ in range(20):
            r = subprocess.run(
                ["docker", "exec", container_name, "redis-cli", "ping"],
                capture_output=True, text=True, timeout=2,
            )
            if r.stdout.strip() == "PONG":
                break
            await asyncio.sleep(0.5)
        return _read_tokenmap_via_cli(
            lambda cmd: subprocess.run(
                ["docker", "exec", container_name, "redis-cli"] + cmd,
                capture_output=True, text=True, check=True,
            ).stdout
        )
    finally:
        subprocess.run(["docker", "stop", container_name], capture_output=True)


async def _import_via_native(tmp_dir: str, rdb_path: str) -> dict[str, str]:
    data_dir = os.path.join(tmp_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    shutil.copy(rdb_path, os.path.join(data_dir, "dump.rdb"))

    # Kill any leftover process on the temp port
    subprocess.run(["fuser", "-k", f"{_TEMP_PORT}/tcp"], capture_output=True)
    time.sleep(0.3)

    log_path = os.path.join(tmp_dir, "redis-temp.log")
    proc = subprocess.Popen(
        [
            "redis-server",
            "--port", str(_TEMP_PORT),
            "--save", "",
            "--appendonly", "no",
            "--dir", data_dir,
            "--dbfilename", "dump.rdb",
            "--loglevel", "verbose",
        ],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    try:
        # Wait for PING
        for _ in range(40):
            r = subprocess.run(
                ["redis-cli", "-p", str(_TEMP_PORT), "ping"],
                capture_output=True, text=True,
            )
            if r.stdout.strip() == "PONG":
                break
            time.sleep(0.5)
        else:
            log = open(log_path).read()[-1000:] if os.path.exists(log_path) else ""
            raise RuntimeError(f"Temp redis on :{_TEMP_PORT} never became ready. Log:\n{log}")

        # Wait for RDB to finish loading (LOADING error goes away)
        for _ in range(30):
            r = subprocess.run(
                ["redis-cli", "-p", str(_TEMP_PORT), "dbsize"],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and "LOADING" not in r.stdout:
                break
            time.sleep(0.3)

        def run_cmd(cmd: list[str]) -> str:
            r = subprocess.run(
                ["redis-cli", "-p", str(_TEMP_PORT)] + cmd,
                capture_output=True, text=True,
            )
            return r.stdout

        return _read_tokenmap_via_cli(run_cmd)
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _read_tokenmap_via_cli(run_cmd) -> dict[str, str]:
    # Scan all keys — dump.rdb may use tokenmap:* or other patterns
    all_keys_out = run_cmd(["keys", "*"])
    all_keys = [k.strip() for k in all_keys_out.splitlines() if k.strip()]

    # Filter to hash keys that look like token maps
    all_entries: dict[str, str] = {}
    for key in all_keys:
        type_out = run_cmd(["type", key]).strip()
        if type_out != "hash":
            continue
        lines = [l.strip() for l in run_cmd(["hgetall", key]).splitlines() if l.strip()]
        for i in range(0, len(lines) - 1, 2):
            all_entries[lines[i]] = lines[i + 1]

    return all_entries
