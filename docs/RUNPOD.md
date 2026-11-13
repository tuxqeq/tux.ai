# Running tux.ai with RAG on RunPod

Code is written and committed on the Mac. The pod only runs it. Decisions: thesis decision log
D-19 (frozen detector v4), D-22 (corpus v2), D-23 (RAG), D-25 (deployment fixes).

## 0. On the Mac, once

1. Commit and push (`git push`).
2. Detector v4 on Hugging Face — **done 2026-11-08**. `tuxqeq/tux-ai-pii-detector`: tag `v3`
   (sha256 of model.safetensors `e9538f67…381d`), tag `v4` and `main` (`5c54c13d…f67d`).
   The commands that did it (for a future model, tag the old one first):

```bash
.venv/bin/python -c "from huggingface_hub import HfApi; HfApi().create_tag('tuxqeq/tux-ai-pii-detector', tag='v3', exist_ok=True)"
.venv/bin/python -c "from huggingface_hub import HfApi; a=HfApi(); a.upload_folder(folder_path='models/pii_model_v4', repo_id='tuxqeq/tux-ai-pii-detector', ignore_patterns=['checkpoint-*'], commit_message='detector v4 (frozen, D-19)'); a.create_tag('tuxqeq/tux-ai-pii-detector', tag='v4', exist_ok=True)"
```

3. Make a Hugging Face **read** token for the pod (Settings → Access Tokens).

## 1. Create the pod

| Setting | Value |
|---|---|
| GPU | 24 GB (RTX 4090, RTX A5000 or L4). `qwen3:4b-instruct-2507-q4_K_M` needs ~4 GB; the rest leaves room for 8B/14B comparisons |
| Template | RunPod PyTorch (Ubuntu 22.04, CUDA 12) |
| Volume | 50 GB, mounted at `/workspace` |
| Ports | **TCP 22 only** ("SSH over exposed TCP"). Do not expose 3000/8000/8080 as HTTP ports |
| SSH key | add your public key in RunPod → Settings → SSH Public Keys |

Why no HTTP ports: the app decrypts PII for an admin. The data is synthetic (Faker), but the
thesis claims an access-controlled system, so the pod is reached only through an SSH tunnel.

## 2. Clone and start the services

```bash
ssh root@<POD_IP> -p <SSH_PORT>
apt-get update -qq && apt-get install -y -qq tmux
cd /workspace && git clone https://github.com/tuxqeq/tux.ai.git && cd tux.ai
tmux new -s app
bash scripts/pod.sh
```

`pod.sh` creates `.env.local` with a random `MASTER_KEY` and `JWT_SECRET` on the first run. Do not
change `MASTER_KEY` later: it wraps the dataset key stored in PostgreSQL.

## 3. RAG setup (second tmux window: `Ctrl-b c`)

```bash
cd /workspace/tux.ai
HF_TOKEN=hf_xxx ADMIN_PASSWORD='choose-one' bash scripts/pod_rag_setup.sh
```

It downloads detector v4 and checks its sha256, pulls `qwen3:4b-instruct-2507-q4_K_M` (not `qwen3:4b`: that tag is the thinking-only 2507 model, its reasoning lands in the answer), generates 1000 documents
(seed 42), tokenizes them (random 32-byte key in `llm/data/dataset_key.b64`, raw files deleted),
creates the dataset, copies the token map, builds the Chroma index and sets the admin password.
Expect 5–15 minutes; tokenization runs on the CPU.

## 4. Open the app through an SSH tunnel (on the Mac)

```bash
ssh -N -L 3000:localhost:3000 root@<POD_IP> -p <SSH_PORT>
```

Open http://localhost:3000, log in as `admin@tux.ai`, choose the dataset **Synthetic corpus v2**.

## 5. Smoke test

```bash
curl -s localhost:8000/api/health        # on the pod: detector "hybrid", pii_model "pii_model_v4"
```

In the chat:

1. "Which people have their primary care at Johns Hopkins Hospital?" → semantic retrieval; the
   answer has `[PERSON_…]` tokens that the UI shows as names (admin sees everything).
2. "What is <one of those names>'s SSN?" → token retrieval: the name in the question is tokenized
   with the dataset key, so it has the same token id as in the records.
3. In the `pod.sh` window, the API log shows `RAG dataset=… records=[('…#0', 'token'), …]`.
4. Ask about a person who is not in the corpus → the model must say that it cannot find it.

## 6. Stop and restart

Kept on `/workspace`: the repo, `.env.local`, Redis `dump.rdb`, `llm/data/` (corpus, key,
dataset id), `data/chroma/` (index), Ollama models (`/workspace/ollama`).
Lost: PostgreSQL (users, chats, the dataset row) — it lives on the container disk.

Before you stop the pod: `redis-cli save`, and copy results to the Mac
(`scp -P <SSH_PORT> -r root@<POD_IP>:/workspace/tux.ai/eval/results ./eval/`).

After a restart: `bash scripts/pod.sh`, then `bash scripts/pod_rag_setup.sh` with
`ADMIN_PASSWORD` again. It re-creates the dataset row with the same id; the token map and the index
are reused.

**Important:** RunPod can start a stopped pod only on the same host. If that host's GPU is taken,
the pod does not start, and a pod volume cannot move to another pod (happened on 2026-11-13,
D-30). Use a **network volume** (RunPod → Storage, same data center as the pod; the account needs
at least $5 of credit to create one) for anything you want to keep across pods.

## 7. Fine-tune vs RAG experiment (D-30)

After sections 2–3 (services running, dataset and index built):

```bash
cd /workspace/tux.ai
sh scripts/pod_ft_eval.sh ftenv        # unsloth venv on the container disk, ~6 min
sh scripts/pod_ft_eval.sh data         # llm/data/qa_v2 + eval/llm_eval_set.jsonl
nohup sh scripts/pod_ft_eval.sh train > /workspace/ft_train.log 2>&1 &   # ~1.5 h, RTX 4090
sh scripts/pod_ft_eval.sh eval-base    # A0 and B; can run while the model trains
sh scripts/pod_ft_eval.sh export       # after training: GGUF -> Ollama tux-ft-qa
sh scripts/pod_ft_eval.sh eval-ft      # A and C
sh scripts/pod_ft_eval.sh summary      # eval/results/summary.md
```

Checkpoints go to `/workspace/ft_runs/qa_v2` every 500 steps. If the pod stops, run `ftenv`
again (the venv was on the container disk) and then `train`: it continues from the last
checkpoint. Copy `eval/results/` to the Mac before you terminate the pod.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ERROR: no token maps of this corpus in Redis` | the Redis dump with the maps is gone, so the corpus cannot be decrypted. Delete `llm/data/tokenized_v2`, `llm/data/dataset_key.b64`, `llm/data/dataset_id` and run the setup again (new key, new corpus) |
| `prepare_corpus.py`: `N file(s) failed` | raw files are kept in `llm/data/raw_temp`; fix the error and run again |
| `/api/health` says `presidio-only` | `models/pii_model_v4/model.safetensors` is missing |
| chat shows `HTTP 404` | the frontend must run through `vite preview` (pod.sh does this), not a plain static server |
| Ollama: model not found | `ollama pull qwen3:4b-instruct-2507-q4_K_M`; the dataset's model is `Dataset.model_name` |
| `tux-ai-chat not found` warning | expected: that fine-tuned model was trained on the old corpus (old key, old token ids) and cannot answer about corpus v2 |
