#!/usr/bin/env bash
# Local development startup.
# Starts PostgreSQL + Redis + Envoy via Docker, then runs API and frontend natively.
# Prerequisites: .venv activated, Docker running, Ollama running (ollama serve or Ollama.app)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# Load env
if [ -f .env.local ]; then
    set -a; source .env.local; set +a
else
    echo "Warning: .env.local not found. Copying .env.example → .env.local with defaults..."
    cp .env.example .env.local
    set -a; source .env.local; set +a
fi

# Ensure venv
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "Error: activate your venv first:  source .venv/bin/activate"
    exit 1
fi

# ── Docker infrastructure ──────────────────────────────────────────────────────

if [ -S /var/run/docker.sock ] && docker info >/dev/null 2>&1; then
    # ── Docker mode ───────────────────────────────────────────────────────────
    echo "[infra] Starting PostgreSQL on :5432..."
    docker volume create tuxai-postgres-data 2>/dev/null || true
    docker run -d --rm --name tuxai-postgres \
        -e POSTGRES_DB=tuxai \
        -e POSTGRES_USER=tuxai \
        -e POSTGRES_PASSWORD=tuxai \
        -p 5432:5432 \
        -v tuxai-postgres-data:/var/lib/postgresql/data \
        postgres:16-alpine \
        2>/dev/null || echo "  PostgreSQL container already running."

    echo "[infra] Starting Redis on :6379..."
    docker volume create tuxai-redis-data 2>/dev/null || true
    docker run -d --rm --name tuxai-redis \
        -p 6379:6379 \
        -v tuxai-redis-data:/data \
        redis:latest \
        redis-server --save 60 1 --loglevel warning \
        2>/dev/null || echo "  Redis container already running."

    echo "[infra] Starting Envoy gRPC-Web proxy on :8080..."
    docker run -d --rm --name tuxai-envoy \
        -p 8080:8080 \
        -v "$ROOT/envoy/envoy.local.yaml:/etc/envoy/envoy.yaml:ro" \
        --add-host=host.docker.internal:host-gateway \
        envoyproxy/envoy:v1.31-latest \
        envoy -c /etc/envoy/envoy.yaml \
        2>/dev/null || echo "  Envoy container already running."

    echo "[infra] Waiting for PostgreSQL to accept connections..."
    for i in $(seq 1 20); do
        if docker exec tuxai-postgres pg_isready -U tuxai -q 2>/dev/null; then
            echo "  PostgreSQL ready."
            break
        fi
        if [ "$i" -eq 20 ]; then
            echo "  ERROR: PostgreSQL did not become ready in time."
            exit 1
        fi
        sleep 1
    done
else
    # ── Native mode (no Docker — Vast.ai / RunPod) ────────────────────────────
    echo "[infra] Docker not available — using native services."

    echo "[infra] Starting PostgreSQL..."
    service postgresql start 2>/dev/null || true
    echo "[infra] Starting Redis..."
    service redis-server start 2>/dev/null || redis-server --daemonize yes --logfile /tmp/redis.log 2>/dev/null || true

    echo "[infra] Waiting for PostgreSQL to accept connections..."
    for i in $(seq 1 20); do
        if pg_isready -U tuxai -q 2>/dev/null; then
            echo "  PostgreSQL ready."
            break
        fi
        if [ "$i" -eq 20 ]; then
            echo "  ERROR: PostgreSQL did not become ready in time."
            exit 1
        fi
        sleep 1
    done

    echo "[infra] Starting Envoy gRPC-Web proxy on :8080..."
    if command -v envoy &>/dev/null; then
        ENVOY_YAML="$ROOT/envoy/envoy.local.yaml"
        [ -f "$ENVOY_YAML" ] || ENVOY_YAML="$ROOT/envoy/envoy.yaml"
        envoy -c "$ENVOY_YAML" --log-level warn &
        echo "  Envoy started."
    else
        echo "  WARNING: envoy not found — gRPC-Web streaming will not work."
        echo "    Install: wget https://github.com/envoyproxy/envoy/releases/download/v1.31.0/envoy-1.31.0-linux-x86_64 -O /usr/local/bin/envoy && chmod +x /usr/local/bin/envoy"
    fi
fi

# Override DATABASE_URL to use localhost (container publishes :5432)
export DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai"
export REDIS_URL="redis://localhost:6379"

# ── Generate gRPC Python stubs ─────────────────────────────────────────────────

echo "[setup] Generating gRPC stubs..."
python -m grpc_tools.protoc \
    -I./proto --python_out=./api/grpc --grpc_python_out=./api/grpc proto/chat.proto
echo "  ✓ api/grpc/chat_pb2.py"

# ── Run Alembic migrations ─────────────────────────────────────────────────────

echo "[setup] Running Alembic migrations..."
DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai" alembic upgrade head
echo "  ✓ Schema up to date."

# ── Check Ollama + model ───────────────────────────────────────────────────────

echo "[check] Checking Ollama..."
OLLAMA_OK=false
if curl -s --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; ms=json.load(sys.stdin).get('models',[]); print(' '.join(m['name'] for m in ms))" 2>/dev/null)
    if echo "$MODELS" | grep -q "tux-ai-chat"; then
        echo "  ✓ Ollama running — tux-ai-chat model found"
        OLLAMA_OK=true
    else
        echo "  WARNING: Ollama is running but tux-ai-chat model is not loaded."
        echo "    Run:  python setup_chat.py"
        echo "    Then: ollama run tux-ai-chat"
    fi
else
    echo "  WARNING: Ollama is not reachable at http://localhost:11434"
    echo "    Start the Ollama app or run:  ollama serve"
    echo "    Then load the model:          python setup_chat.py"
fi

echo "[check] Checking PII model..."
for MODEL_DIR in models/pii_model_v2 models/pii_model_advanced models/pii_model_large models/pii_model; do
    if [ -f "$ROOT/$MODEL_DIR/model.safetensors" ]; then
        echo "  ✓ Using PII model: $MODEL_DIR"
        export MODEL_PATH="$MODEL_DIR"
        break
    fi
done
if [ -z "${MODEL_PATH:-}" ]; then
    echo "  WARNING: No trained model found in models/. Falling back to Presidio-only detection."
    echo "    Train a model first:  python src/train.py --smoke_test"
fi

# ── npm install (if needed) ────────────────────────────────────────────────────

if [ ! -d frontend/node_modules ]; then
    echo "[frontend] Installing npm dependencies..."
    (cd frontend && npm install --silent)
fi

# ── Start backend ──────────────────────────────────────────────────────────────

echo "[api] Starting FastAPI on :8000..."
DATABASE_URL="postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai" \
REDIS_URL="redis://localhost:6379" \
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# ── Start frontend ─────────────────────────────────────────────────────────────

if [ -S /var/run/docker.sock ] && docker info >/dev/null 2>&1; then
    # Local dev — use Vite hot-reload
    echo "[frontend] Starting Vite dev server on :5173..."
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    cd "$ROOT"
    FRONTEND_URL="http://localhost:5173"
else
    # Pod / server — build once and serve statically on :3000
    echo "[frontend] Building for production..."
    (cd frontend && npm run build --silent)
    echo "[frontend] Serving on :3000..."
    npx --yes serve frontend/dist -l 3000 &
    FRONTEND_PID=$!
    FRONTEND_URL="http://0.0.0.0:3000"
fi

echo ""
echo "  ┌──────────────────────────────────────────┐"
printf  "  │  App       →  %-27s│\n" "$FRONTEND_URL"
echo "  │  API       →  http://0.0.0.0:8000        │"
echo "  │  gRPC-Web  →  http://0.0.0.0:8080        │"
echo "  └──────────────────────────────────────────┘"
echo ""
echo "  Admin:  admin@tux.ai / admin"
echo "  Press Ctrl+C to stop."

cleanup() {
    echo ""
    echo "Stopping services..."
    kill "$API_PID" "$FRONTEND_PID" 2>/dev/null || true
    docker stop tuxai-envoy tuxai-postgres tuxai-redis 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM
wait
