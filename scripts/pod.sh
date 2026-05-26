#!/usr/bin/env bash
# Vast.ai / RunPod startup — no Docker required.
# Installs and starts PostgreSQL + Redis + Envoy natively, then runs API + frontend.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# ── Load env ───────────────────────────────────────────────────────────────────
if [ -f .env.local ]; then
    set -a; source .env.local; set +a
else
    echo "Warning: .env.local not found. Copying .env.example → .env.local..."
    cp .env.example .env.local
    set -a; source .env.local; set +a
fi

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
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='tuxai'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER tuxai WITH PASSWORD 'tuxai';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='tuxai'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE tuxai OWNER tuxai;"
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

# Use local yaml (points to 127.0.0.1 instead of docker host alias)
ENVOY_YAML="envoy/envoy.local.yaml"
if [ ! -f "$ENVOY_YAML" ]; then
    ENVOY_YAML="envoy/envoy.yaml"
fi
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
for MODEL_DIR in models/pii_model_v2 models/pii_model_advanced models/pii_model_large models/pii_model; do
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

echo "[frontend] Serving on :3000..."
npx --yes serve frontend/dist -l 3000 &
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
