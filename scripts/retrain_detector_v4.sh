#!/usr/bin/env bash
# pii_model_v4: Nemotron-PII documents (train split) + Faker train-split templates.
# Decision log D-13. Run on the Mac, keep it awake:
#   caffeinate -i bash scripts/retrain_detector_v4.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi

mkdir -p logs
LOG="logs/retrain_detector_v4_$(date +%Y%m%d_%H%M).log"
exec > >(tee -a "$LOG") 2>&1
echo "Log: $LOG"

echo "== 1/4 training mix + dev set"
python src/build_train_mix.py

echo "== 2/4 smoke test"
python src/train.py --smoke_test --max_length 128 --output_dir /tmp/pii_smoke_test_v4

echo "== 3/4 full training (3 epochs, fixed length 128)"
python src/train.py --data_file data/train_data_v4.json --epochs 3 --max_length 128 --output_dir models/pii_model_v4

echo "== 4/4 check: AI layer loads"
python src/hybrid_detect.py --model-path models/pii_model_v4 --text "Contact John Smith at john.smith@example.com, password River2021#."
echo "Done. Model: models/pii_model_v4  Log: $LOG"
