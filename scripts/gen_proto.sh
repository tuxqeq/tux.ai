#!/usr/bin/env bash
# Generate gRPC stubs for Python and TypeScript from proto/chat.proto
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

echo "[1/2] Generating Python stubs..."
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./api/grpc \
    --grpc_python_out=./api/grpc \
    proto/chat.proto
echo "  ✓ api/grpc/chat_pb2.py, api/grpc/chat_pb2_grpc.py"

echo "[2/2] Generating TypeScript stubs (requires protoc + protoc-gen-grpc-web)..."
if ! command -v protoc &>/dev/null; then
    echo "  SKIP: protoc not found — install with: brew install protobuf"
    echo "  Frontend uses the manual fetch-based gRPC-Web client (src/lib/grpc-client.ts)"
    exit 0
fi
if ! command -v protoc-gen-grpc-web &>/dev/null; then
    echo "  SKIP: protoc-gen-grpc-web not found — install from:"
    echo "        https://github.com/grpc/grpc-web/releases"
    exit 0
fi

mkdir -p frontend/src/proto
protoc \
    --plugin="protoc-gen-grpc-web=$(which protoc-gen-grpc-web)" \
    --js_out="import_style=commonjs:frontend/src/proto" \
    --grpc-web_out="import_style=typescript,mode=grpcwebtext:frontend/src/proto" \
    -I./proto \
    proto/chat.proto
echo "  ✓ frontend/src/proto/chat_pb.js, frontend/src/proto/ChatServiceClientPb.ts"
