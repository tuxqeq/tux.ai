#!/usr/bin/env bash
# Final detector report (thesis decision log D-18): pii_model_v3 vs pii_model_v4 on three test sets
# with the production settings (word-level AI, span union, label rule ai_first, no Presidio
# threshold, no AI format checks). Settings were chosen on the Nemotron-PII DEV set only.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
mkdir -p logs
LOG="logs/final_report_$(date +%Y%m%d_%H%M).log"
exec > >(tee -a "$LOG") 2>&1
echo "Log: $LOG"

if [ ! -f data/external_ai4privacy_en_1000.json ]; then
  python eval/prepare_external.py --source ai4privacy
fi

for DATA in data/test_heldout_templates.json data/external_nemotron_test_1000.json data/external_ai4privacy_en_1000.json; do
  for MODEL in models/pii_model_v3 models/pii_model_v4; do
    echo "== $DATA  $MODEL"
    python eval/eval_detector.py --data "$DATA" --model-path "$MODEL" \
      --modes presidio,ai_word,hybrid_word_union --save-preds | tail -6
  done
done

echo "== summary"
python eval/summarize_results.py
