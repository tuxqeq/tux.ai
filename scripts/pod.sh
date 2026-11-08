#!/usr/bin/env bash
# Vast.ai / RunPod startup — no Docker required.
# Installs and starts PostgreSQL + Redis + Envoy natively, then runs API + frontend.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# ── Load env ───────────────────────────────────────────────────────────────────
# A pod is reachable from the internet: never run it with the example secrets. MASTER_KEY wraps the
# dataset keys in PostgreSQL, so it must stay the same for the life of a dataset (.env.local lives
# in the repo, i.e. on the /workspace volume).
if [ ! -f .env.local ]; then
    echo "[env] .env.local not found: creating it with random MASTER_KEY and JWT_SECRET"
    python3 - <<'PY'
import secrets, string, re
alphabet = string.ascii_letters + string.digits
rnd = lambda n: "".join(secrets.choice(alphabet) for _ in range(n))
s = open(".env.example").read()
s = re.sub(r"^MASTER_KEY=.*$", "MASTER_KEY=" + rnd(32), s, flags=re.M)
s = re.sub(r"^JWT_SECRET=.*$", "JWT_SECRET=" + rnd(48), s, flags=re.M)
open(".env.local", "w").write(s)
PY
    chmod 600 .env.local
fi
set -a; source .env.local; set +a
if grep -q "CHANGE_ME" .env.local; then
    echo "ERROR: .env.local still has a CHANGE_ME secret. Set MASTER_KEY and JWT_SECRET first."
    exit 1
fi

# Ollama models on the volume, so a pod restart does not download them again
if [ -d /workspace ]; then
    export OLLAMA_MODELS="${OLLAMA_MODELS:-/workspace/ollama}"
    mkdir -p "$OLLAMA_MODELS"
fi

as_postgres() {  # RunPod images often have no sudo
    if command -v sudo &>/dev/null; then sudo -u postgres "$@"; else su postgres -c "$(printf '%q ' "$@")"; fi
}

export DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai"
export REDIS_URL="redis://localhost:6379"

# ── System packages ────────────────────────────────────────────────────────────
echo "[infra] Installing system packages..."
apt-get update -qq
apt-get install -y -qq postgresql redis-server curl wget nodejs npm 2>/dev/null || true

# ── PostgreSQL ─────────────────────────────────────────────────────────────────
echo "[infra] Starting PostgreSQL..."
service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || true

sleep 2

# Create user/db if they don't exist
as_postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='tuxai'" | grep -q 1 || \
    as_postgres psql -c "CREATE USER tuxai WITH PASSWORD 'tuxai';"
as_postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='tuxai'" | grep -q 1 || \
    as_postgres psql -c "CREATE DATABASE tuxai OWNER tuxai;"
echo "  ✓ PostgreSQL ready"

# ── Redis ──────────────────────────────────────────────────────────────────────
echo "[infra] Starting Redis..."
redis-server --daemonize yes --logfile /tmp/redis.log --save 60 1 2>/dev/null || true
sleep 1
redis-cli ping | grep -q PONG && echo "  ✓ Redis ready" || echo "  WARNING: Redis not responding"

# ── Envoy gRPC-Web proxy ───────────────────────────────────────────────────────
echo "[infra] Setting up Envoy..."
if ! command -v envoy &>/dev/null; then
    echo "  Downloading Envoy binary..."
    ENVOY_VERSION="1.31.0"
    wget -q "https://github.com/envoyproxy/envoy/releases/download/v${ENVOY_VERSION}/envoy-${ENVOY_VERSION}-linux-x86_64" \
        -O /usr/local/bin/envoy
    chmod +x /usr/local/bin/envoy
fi

# envoy.local.yaml targets host.docker.internal (Envoy in Docker, see dev.sh); on the pod Envoy runs
# natively next to the API, so point it at 127.0.0.1
ENVOY_YAML="/tmp/envoy.pod.yaml"
sed 's/host\.docker\.internal/127.0.0.1/' envoy/envoy.local.yaml > "$ENVOY_YAML"
envoy -c "$ENVOY_YAML" --log-level warn &
ENVOY_PID=$!
echo "  ✓ Envoy started (gRPC-Web on :8080)"

# ── Python venv ────────────────────────────────────────────────────────────────
if [ ! -d .venv ]; then
    echo "[setup] Creating virtualenv..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "[setup] Installing Python dependencies..."
pip install -q -r requirements.txt -r requirements.api.txt

# ── gRPC stubs ─────────────────────────────────────────────────────────────────
echo "[setup] Generating gRPC stubs..."
python -m grpc_tools.protoc \
    -I./proto --python_out=./api/grpc --grpc_python_out=./api/grpc proto/chat.proto
echo "  ✓ api/grpc/chat_pb2.py"

# ── Alembic migrations ─────────────────────────────────────────────────────────
echo "[setup] Running migrations..."
DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai" alembic upgrade head
echo "  ✓ Schema up to date"

# ── Ollama ─────────────────────────────────────────────────────────────────────
echo "[check] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! pgrep -x ollama &>/dev/null; then
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
fi

if curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c \
        "import sys,json; ms=json.load(sys.stdin).get('models',[]); print(' '.join(m['name'] for m in ms))" 2>/dev/null)
    if echo "$MODELS" | grep -q "tux-ai-chat"; then
        echo "  ✓ tux-ai-chat model ready"
    else
        echo "  WARNING: tux-ai-chat not found."
        echo "    Run: python setup_chat.py"
    fi
else
    echo "  WARNING: Ollama not reachable — run: ollama serve &"
fi

# ── PII model ──────────────────────────────────────────────────────────────────
for MODEL_DIR in models/pii_model_v4 models/pii_model_v3 models/pii_model_v2 models/pii_model; do
    if [ -f "$ROOT/$MODEL_DIR/model.safetensors" ]; then
        echo "  ✓ PII model: $MODEL_DIR"
        export MODEL_PATH="$MODEL_DIR"
        break
    fi
done
if [ -z "${MODEL_PATH:-}" ]; then
    echo "  WARNING: No PII model found — falling back to Presidio-only"
fi

# ── Frontend ───────────────────────────────────────────────────────────────────
if [ ! -d frontend/node_modules ]; then
    echo "[frontend] Installing npm dependencies..."
    (cd frontend && npm install --silent)
fi

echo "[frontend] Building frontend..."
(cd frontend && npm run build --silent)

# vite preview serves dist/ WITH the proxy of vite.config.ts (/api -> :8000, /chat.ChatService -> :8080);
# a plain static server (the old `npx serve`) answered those paths with 404
echo "[frontend] Serving on :3000..."
(cd frontend && npx vite preview --host 0.0.0.0 --port 3000 --strictPort) &
FRONTEND_PID=$!

# ── API ────────────────────────────────────────────────────────────────────────
echo "[api] Starting FastAPI on :8000..."
DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai" \
REDIS_URL="redis://localhost:6379" \
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo ""
echo "  ┌──────────────────────────────────────────┐"
echo "  │  App       →  http://0.0.0.0:3000        │"
echo "  │  API       →  http://0.0.0.0:8000        │"
echo "  │  gRPC-Web  →  http://0.0.0.0:8080        │"
echo "  └──────────────────────────────────────────┘"
echo ""
echo "  Admin:  admin@tux.ai / admin"
echo "  Press Ctrl+C to stop."

cleanup() {
    echo "Stopping services..."
    kill "$API_PID" "$FRONTEND_PID" "$ENVOY_PID" 2>/dev/null || true
    redis-cli shutdown 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM
wait
