#!/bin/bash
# pod_ft_all.sh — whole D-30 run on a fresh pod, unattended (docs/RUNPOD.md, sections 2, 3, 7).
#   cd /workspace/tux.ai && nohup bash scripts/pod_ft_all.sh > /workspace/ft_all.log 2>&1 &
# Needs HF_TOKEN in the pod environment (RunPod secret). Logs: /workspace/*.log.
# Every step can be re-run: pod.sh and the setup reuse what is already on /workspace,
# training continues from its last checkpoint, evaluation resumes its result files.
cd "$(dirname "$0")/.."
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

PW_FILE=/workspace/admin_password
[ -s "$PW_FILE" ] || (umask 077; openssl rand -base64 15 > "$PW_FILE")

log "services (pod.sh)"
nohup bash scripts/pod.sh > /workspace/pod.log 2>&1 &
log "fine-tune env (in parallel)"
sh scripts/pod_ft_eval.sh ftenv > /workspace/ftenv.log 2>&1 &
FTENV_PID=$!

for i in $(seq 1 180); do
  curl -sf localhost:8000/api/health > /dev/null && break
  sleep 10
done
curl -sf localhost:8000/api/health > /dev/null || { log "API did not start, see /workspace/pod.log"; exit 1; }

log "RAG setup (corpus v2, dataset, index)"
ADMIN_PASSWORD="$(cat "$PW_FILE")" bash scripts/pod_rag_setup.sh > /workspace/rag_setup.log 2>&1 \
  || { log "pod_rag_setup failed, see /workspace/rag_setup.log"; exit 1; }

log "QA data + eval set"
sh scripts/pod_ft_eval.sh data > /workspace/ft_data.log 2>&1 || { log "data failed"; exit 1; }

wait "$FTENV_PID" || { log "ftenv failed, see /workspace/ftenv.log"; exit 1; }
log "training"
sh scripts/pod_ft_eval.sh train > /workspace/ft_train.log 2>&1 &
TRAIN_PID=$!

sleep 240   # let the trainer load the model before Ollama takes GPU memory
log "eval A0, B (base model)"
sh scripts/pod_ft_eval.sh eval-base > /workspace/eval_base.log 2>&1 || log "eval-base failed"

wait "$TRAIN_PID" || { log "training failed, see /workspace/ft_train.log"; exit 1; }
log "export to Ollama"
sh scripts/pod_ft_eval.sh export > /workspace/ft_export.log 2>&1 || { log "export failed"; exit 1; }
log "eval A, C (fine-tuned model)"
sh scripts/pod_ft_eval.sh eval-ft > /workspace/eval_ft.log 2>&1 || log "eval-ft failed"
sh scripts/pod_ft_eval.sh summary > /workspace/summary.log 2>&1
log "ALL_DONE"
