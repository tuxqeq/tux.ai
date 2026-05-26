#!/usr/bin/env bash
# Login and print JWT + CSRF tokens ready for curl use.
# Usage:
#   bash scripts/get_tokens.sh                        # print tokens + dataset list
#   bash scripts/get_tokens.sh --import-rdb <ds_id>  # import dump.rdb from server
#   bash scripts/get_tokens.sh --register-model <ds_id>  # register GGUF from server

EMAIL="${EMAIL:-admin@tux.ai}"
PASS="${PASS:-admin}"
API="${API:-http://localhost:8000}"
RDB_PATH="${RDB_PATH:-/workspace/tux.ai/dump.rdb}"
GGUF_PATH="${GGUF_PATH:-/workspace/tux.ai/llm/export/Model Q8 0.gguf}"

MODE="${1:-}"
DS_ID="${2:-}"

RESPONSE=$(curl -si -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASS\"}")

JWT=$(echo "$RESPONSE" | grep -i "set-cookie" | grep "access_token" | sed 's/.*access_token=\([^;]*\).*/\1/')
CSRF=$(echo "$RESPONSE" | grep -i "set-cookie" | grep "csrf_token" | sed 's/.*csrf_token=\([^;]*\).*/\1/')
COOKIE_HEADER="access_token=$JWT; csrf_token=$CSRF"

if [ -z "$JWT" ]; then
  echo "Login failed. Response:"
  echo "$RESPONSE" | tail -5
  exit 1
fi

DATASETS=$(curl -s "$API/api/admin/datasets" \
  -H "Cookie: $COOKIE_HEADER")

echo "JWT:  $JWT"
echo "CSRF: $CSRF"
echo ""
echo "Datasets:"
echo "$DATASETS" | python3 -c "
import sys, json
ds = json.load(sys.stdin)
for d in ds:
    print(f\"  {d['id']}  {d['name']}  (key={'yes' if d['has_key'] else 'no'}, rdb={'yes' if d.get('rdb_imported') else 'no'}, model={d.get('model_name') or 'none'})\")
" 2>/dev/null || echo "$DATASETS"
echo ""
echo "# Paste these into your curl commands:"
echo "COOKIE=\"access_token=$JWT\""
echo "CSRF=\"$CSRF\""
echo ""
if [ "$MODE" = "--import-rdb" ]; then
  [ -z "$DS_ID" ] && echo "Usage: $0 --import-rdb <dataset_id>" && exit 1
  echo "Importing RDB from $RDB_PATH ..."
  curl -s -X POST "$API/api/admin/datasets/$DS_ID/import-rdb-path" \
    -H "Content-Type: application/json" \
    -H "Cookie: $COOKIE_HEADER" \
    -H "X-CSRF-Token: $CSRF" \
    -d "{\"path\": \"$RDB_PATH\"}"
  echo ""

elif [ "$MODE" = "--register-model" ]; then
  [ -z "$DS_ID" ] && echo "Usage: $0 --register-model <dataset_id>" && exit 1
  echo "Registering GGUF from $GGUF_PATH ..."
  curl -s -X POST "$API/api/admin/datasets/$DS_ID/register-model-path" \
    -H "Content-Type: application/json" \
    -H "Cookie: $COOKIE_HEADER" \
    -H "X-CSRF-Token: $CSRF" \
    -d "{\"path\": \"$GGUF_PATH\"}"
  echo ""

else
  echo "# Run with --import-rdb <ds_id> or --register-model <ds_id>"
fi
