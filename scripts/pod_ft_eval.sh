#!/bin/sh
# pod_ft_eval.sh — D-30 on the pod: closed-book fine-tune vs RAG (docs/RUNPOD.md, section 7).
# Run after scripts/pod.sh (services) and scripts/pod_rag_setup.sh (corpus v2, dataset, index).
#   sh scripts/pod_ft_eval.sh ftenv     # unsloth venv (/root/ft) + llama.cpp converter, ~6 min
#   sh scripts/pod_ft_eval.sh data      # QA training data + eval questions from corpus v2
#   sh scripts/pod_ft_eval.sh train     # QLoRA on Qwen3-4B-Instruct-2507, ~1.5 h on an RTX 4090;
#                                       # checkpoints on /workspace, re-run continues from the last one
#   sh scripts/pod_ft_eval.sh export    # merged model -> GGUF f16 -> Ollama "tux-ft-qa" (q4_K_M)
#   sh scripts/pod_ft_eval.sh eval-base # configs A0 and B (base model); can run during training
#   sh scripts/pod_ft_eval.sh eval-ft   # configs A and C (fine-tuned model)
#   sh scripts/pod_ft_eval.sh summary   # eval/results/summary.md
# The container disk is wiped when the pod stops: keep outputs on /workspace (RUN, GGUF_DIR).
set -e
cd "$(dirname "$0")/.."
BASE_MODEL="${BASE_MODEL:-qwen3:4b-instruct-2507-q4_K_M}"
FT_MODEL="${FT_MODEL:-tux-ft-qa}"
RUN="${RUN:-/workspace/ft_runs/qa_v2}"
GGUF_DIR="${GGUF_DIR:-/workspace/gguf}"
FT_VENV="${FT_VENV:-/root/ft}"
FT_PY="$FT_VENV/bin/python"
LLAMA_CPP="${LLAMA_CPP:-/root/llama.cpp}"
APP_PY="${APP_PY:-.venv/bin/python}"

case "$1" in
  ftenv)
    [ -x "$FT_PY" ] || python3 -m venv --system-site-packages "$FT_VENV"
    "$FT_PY" -m pip install -q -U pip
    "$FT_PY" -m pip install -q unsloth gguf sentencepiece
    [ -d "$LLAMA_CPP" ] || git clone -q --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_CPP"
    "$FT_PY" -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())' ;;
  data)
    python3 llm/build_qa_dataset.py --corpus-dir llm/data/tokenized_v2 ;;
  train)
    HF_HOME="${HF_HOME:-/workspace/hf-cache}" "$FT_PY" llm/train_qlora.py \
      --train-file llm/data/qa_v2/train.jsonl --val-file llm/data/qa_v2/val.jsonl \
      --output-dir "$RUN" --base-model unsloth/Qwen3-4B-Instruct-2507 \
      --epochs 3 --lr 2e-4 --batch-size 16 --grad-accum 1 --max-seq-length 1024 \
      --lora-rank 64 --lora-alpha 64 --save-steps 500 --save-total-limit 2 \
      --eval-steps 1000 --max-val 300 --resume ;;
  export)
    mkdir -p "$GGUF_DIR"
    "$FT_PY" "$LLAMA_CPP/convert_hf_to_gguf.py" "$RUN/merged_16bit" \
      --outtype f16 --outfile "$GGUF_DIR/$FT_MODEL-f16.gguf"
    # same chat template, stop tokens and parameters as the base model
    ollama show "$BASE_MODEL" --modelfile \
      | sed -e "s|^FROM .*|FROM $GGUF_DIR/$FT_MODEL-f16.gguf|" > "$GGUF_DIR/$FT_MODEL.Modelfile"
    ollama create "$FT_MODEL" -q q4_K_M -f "$GGUF_DIR/$FT_MODEL.Modelfile"
    ollama list | grep -E "$FT_MODEL|$BASE_MODEL" ;;
  eval-base)
    DS="$(cat llm/data/dataset_id)"
    "$APP_PY" eval/eval_llm.py --config A0 --model "$BASE_MODEL"
    "$APP_PY" eval/eval_llm.py --config B --model "$BASE_MODEL" --dataset-id "$DS" ;;
  eval-ft)
    DS="$(cat llm/data/dataset_id)"
    "$APP_PY" eval/eval_llm.py --config A --model "$FT_MODEL"
    "$APP_PY" eval/eval_llm.py --config C --model "$FT_MODEL" --dataset-id "$DS" ;;
  summary)
    "$APP_PY" eval/eval_llm.py --summarize ;;
  *)
    echo "usage: $0 ftenv|data|train|export|eval-base|eval-ft|summary"; exit 2 ;;
esac
