#!/usr/bin/env bash
# RAG setup on the RunPod pod (thesis decision log D-23). Run it in a second terminal while
# scripts/pod.sh is running (it starts Redis, PostgreSQL + migrations, Ollama and the API).
# Safe to run again, also after a pod restart.
#
#   HF_TOKEN=hf_... ADMIN_PASSWORD='...' bash scripts/pod_rag_setup.sh
#
# Env: HF_TOKEN        read access to the private repo tuxqeq/tux-ai-pii-detector (first run only)
#      RAG_MODEL       Ollama model for the dataset's chats (default qwen3:4b)
#      DOC_COUNT       synthetic documents (default 1000, seed 42)
#      ADMIN_PASSWORD  new password for admin@tux.ai (the migration seeds "admin")
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"
source .venv/bin/activate
set -a; source .env.local; set +a
export DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai"
export REDIS_URL="redis://localhost:6379"
export TOKENIZERS_PARALLELISM=false
RAG_MODEL="${RAG_MODEL:-qwen3:4b}"
DOC_COUNT="${DOC_COUNT:-1000}"
# sha256 of the frozen detector (D-19): models/pii_model_v4/model.safetensors on the training Mac
V4_SHA256="5c54c13de6fe6b5a5a0f8770e3161e46d22c3ef2c97bb1d7dfd01f9fc076f67d"

echo "[1/6] PII detector v4"
if [ ! -f models/pii_model_v4/model.safetensors ]; then
    : "${HF_TOKEN:?set HF_TOKEN (read access to tuxqeq/tux-ai-pii-detector)}"
    python -c "from huggingface_hub import snapshot_download; snapshot_download('tuxqeq/tux-ai-pii-detector', revision='v4', local_dir='models/pii_model_v4')"
fi
GOT="$(sha256sum models/pii_model_v4/model.safetensors | cut -d' ' -f1)"
if [ "$GOT" != "$V4_SHA256" ]; then
    echo "ERROR: models/pii_model_v4 is not the frozen v4 detector (sha256 $GOT)"
    exit 1
fi
echo "  ok (sha256 matches the frozen v4)"

echo "[2/6] spaCy model for Presidio"
python -c "import spacy; spacy.load('en_core_web_lg')" 2>/dev/null || python -m spacy download en_core_web_lg

echo "[3/6] Ollama model $RAG_MODEL"
ollama pull "$RAG_MODEL"

echo "[4/6] Corpus v2 ($DOC_COUNT documents, seed 42)"
if [ -z "$(ls -A llm/data/tokenized_v2 2>/dev/null)" ]; then
    python llm/generate_synthetic_docs.py --count "$DOC_COUNT" --seed 42 --output-dir llm/data/raw_temp
    python llm/prepare_corpus.py --input-dir llm/data/raw_temp --output-dir llm/data/tokenized_v2
else
    echo "  llm/data/tokenized_v2 exists: skipped"
fi

echo "[5/6] Dataset, token map and RAG index"
ID_FILE=llm/data/dataset_id
ARGS=(--model "$RAG_MODEL")
if [ -f "$ID_FILE" ]; then ARGS+=(--dataset-id "$(cat "$ID_FILE")"); fi
python scripts/bootstrap_dataset.py "${ARGS[@]}" | tee /tmp/bootstrap.log
grep -o 'DATASET_ID=[0-9a-f-]*' /tmp/bootstrap.log | cut -d= -f2 > "$ID_FILE"

echo "[6/6] Admin password"
if [ -n "${ADMIN_PASSWORD:-}" ]; then
    python - <<'PY'
import asyncio, os
from sqlalchemy import update
from api.db import AsyncSessionLocal
from api.models import User
from api.security import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == "admin@tux.ai")
                         .values(hashed_password=hash_password(os.environ["ADMIN_PASSWORD"])))
        await db.commit()

asyncio.run(main())
print("  admin@tux.ai password changed")
PY
else
    echo "  WARNING: admin@tux.ai still has the password 'admin'. Use the SSH tunnel only,"
    echo "           or run again with ADMIN_PASSWORD=..."
fi

echo ""
echo "Done. Dataset id: $(cat "$ID_FILE")"
echo "If you chatted with this dataset before this run, restart scripts/pod.sh (Chroma is not multi-process safe)."
