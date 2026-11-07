#!/usr/bin/env bash
# Retrain the DistilBERT PII detector -> models/pii_model_v3
#
#   1. Train data from the TRAIN template split only (~80% of templates).
#   2. Held-out test set from the TEST template split (for Phase 1 evaluation).
#   3. Smoke test, then the full run (5 epochs, same settings as pii_model_v2).
#
# Run on the Mac (MPS), keep it awake:
#   caffeinate -i bash scripts/retrain_detector.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi

mkdir -p logs
LOG="logs/retrain_detector_$(date +%Y%m%d_%H%M).log"
exec > >(tee -a "$LOG") 2>&1
echo "Log: $LOG"
python -c "from importlib.metadata import version as v; import torch; print('faker', v('faker'), '| transformers', v('transformers'), '| torch', torch.__version__, '| mps', torch.backends.mps.is_available())"

echo "== 1/5 train data (train templates, seed 42)"
python src/generate_data.py --split train --seed 42 --count 100000 --output data/train_data_v3.json

echo "== 2/5 held-out test set (test templates, seed 7)"
python src/generate_data.py --split test --seed 7 --count 5000 --output data/test_heldout_templates.json

echo "== 3/5 smoke test"
python src/train.py --smoke_test --output_dir /tmp/pii_smoke_test

echo "== 4/5 full training (5 epochs)"
python src/train.py --data_file data/train_data_v3.json --epochs 5 --output_dir models/pii_model_v3

echo "== 5/5 check: AI layer loads"
python src/hybrid_detect.py --text "Contact John Smith at john.smith@example.com or 555-123-4567."
echo "Done. Model: models/pii_model_v3  Log: $LOG"
