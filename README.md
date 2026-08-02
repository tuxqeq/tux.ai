# tux.ai

**Chat with an LLM over sensitive documents without the plaintext PII ever leaving your control.**

tux.ai detects personally identifiable information, replaces it with reversible placeholder tokens
(`[PERSON_a1b2c3d4]`), and encrypts the originals. The chat model is fine-tuned on tokenized text only —
it has never seen a real name, SSN, or card number. At read time, a role-based access control layer
decrypts *only* the entity types a given user is authorized to see. Everyone else sees the token.

Plaintext PII is never written to the application database.

---

## How it works

```
┌─ Browser ────────────────────────────────────────────────────────────────┐
│  React 18 + TypeScript + Tailwind                                        │
│    ├─ REST (auth, admin, chat history)  ──────────────┐                  │
│    └─ gRPC-Web (streaming chat)  ──► Envoy :8080 ──┐  │                  │
└────────────────────────────────────────────────────┼──┼──────────────────┘
                                                     │  │
┌─ Backend (one asyncio event loop) ─────────────────▼──▼──────────────────┐
│  gRPC :50051  +  FastAPI :8000                                           │
│    │                                                                     │
│    ├─► tokenize user message   (Presidio + DistilBERT)                    │
│    ├─► PostgreSQL   sessions · messages (tokenized) · users · RBAC · audit│
│    ├─► Redis        token → AES-encrypted original                        │
│    └─► Ollama       tux-ai-chat (Qwen3, QLoRA-tuned on tokenized text)     │
│              │                                                            │
│              └─► stream out ─► RBAC decrypt per chunk ─► audit log        │
└──────────────────────────────────────────────────────────────────────────┘
```

**1. Detection** — hybrid. Microsoft Presidio supplies rule-based recognizers (17 built-ins + 23 custom
patterns in [recognizers.py](src/recognizers.py)); a fine-tuned DistilBERT token classifier catches
contextual PII that regex misses. Overlapping spans from both sources are merged and deduplicated.

**2. Tokenization** — each detected span becomes `[LABEL_hexid]`. The original value is AES-encrypted and
stored in Redis under the session's token map. The dataset's AES key is itself wrapped with the server
`MASTER_KEY` (AES-256-GCM) before being stored in Postgres.

**3. Chat** — the user's message is tokenized *before* it is persisted or sent to the model. The model
replies in tokenized form. Assistant messages are stored tokenized too.

**4. RBAC** — grants are per-user × per-dataset × per-entity-type. As each streamed chunk comes back from
Ollama, [decryptor.py](api/services/decryptor.py) substitutes plaintext for the tokens whose entity type
the user is granted, and leaves the rest untouched. Admins hold a `*` wildcard. Every substitution is
written to the audit log.

---

## Services

| Service    | Port  | Purpose                                                    |
|------------|-------|------------------------------------------------------------|
| Frontend   | 3000  | React SPA (nginx in Docker; Vite dev server uses 5173)     |
| FastAPI    | 8000  | REST — auth, admin, chat history, health                    |
| Envoy      | 8080  | gRPC-Web → gRPC translation for the browser                 |
| gRPC       | 50051 | `ChatService.StreamChat` (internal — reached via Envoy)      |
| PostgreSQL | 5432  | Users, datasets, encryption keys, RBAC grants, chats, audit |
| Redis      | 6379  | Token → encrypted-value recovery map                        |
| Ollama     | 11434 | LLM inference (`tux-ai-chat`)                               |

---

## Quick start

### Prerequisites

- Docker + Docker Compose
- [Ollama](https://ollama.com) running on the host (`ollama serve`, or the desktop app).
  Alternatively uncomment the `ollama` service in [docker-compose.yml](docker-compose.yml) for CPU-only.
- Python 3.11+ if you want the CLI tools or the training pipelines

### 1. Get the chat model

```bash
pip install huggingface_hub
python setup_chat.py
```

This downloads the pre-built GGUF (~8 GB) from the `tuxqeq/tux-ai-chat` HF repo, writes an Ollama
`Modelfile` with the correct Qwen3 chat template and system prompt, and registers it as `tux-ai-chat`.
It also reports whether a PII detector model is present in `models/`.

Flags: `--force` (re-download and recreate), `--skip-ollama` (download only).

> Prefer to train your own? See [LLM fine-tuning](#llm-fine-tuning-pipeline) below.
> No PII model in `models/`? Everything still runs — detection silently falls back to Presidio-only.

### 2. Configure

```bash
cp .env.example .env.local
```

At minimum, replace `MASTER_KEY` and `JWT_SECRET` with random 32-character strings.

### 3. Start

```bash
docker compose up --build
```

The `api` container generates the gRPC stubs and runs `alembic upgrade head` on startup, so the schema
is created for you.

Open **http://localhost:3000** and log in:

```
admin@tux.ai / admin      ← seeded by migration 0001; change it immediately
```

Health check: `http://localhost:8000/api/health`. (Interactive OpenAPI docs are disabled in
[main.py](api/main.py#L25) — set `docs_url="/docs"` if you want them locally.)

---

## Local development

The fastest path is the dev script — it starts Postgres, Redis, and Envoy as containers, generates gRPC
stubs, runs migrations, checks Ollama and the PII model, then runs the API and Vite natively with
hot reload:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements.api.txt
bash scripts/dev.sh
```

App on `:5173`, API on `:8000`, gRPC-Web on `:8080`. Ctrl+C tears the containers back down.

<details>
<summary>Manual setup, if you'd rather run each piece yourself</summary>

```bash
# Dependencies
brew services start postgresql@16 redis
ollama serve &

# Create the database (once)
createuser -s tuxai; createdb -O tuxai tuxai

# gRPC stubs + schema
bash scripts/gen_proto.sh
alembic upgrade head

# Backend
uvicorn api.main:app --reload

# Frontend (separate shell)
cd frontend && npm install && npm run dev
```
</details>

### On a GPU pod (Vast.ai / RunPod, no Docker)

```bash
bash scripts/pod.sh
```

Installs and starts Postgres, Redis, Envoy, and Ollama natively, builds the frontend, and serves it
statically on `:3000`.

---

## Configuration

All settings live in `.env.local` and are loaded by [api/config.py](api/config.py).

| Variable       | Default                                                | Notes                                              |
|----------------|--------------------------------------------------------|----------------------------------------------------|
| `MASTER_KEY`   | `CHANGE_ME_MASTER_KEY_32_bytes!!!`                      | **Change this.** Exactly 32 bytes. Wraps dataset AES keys at rest. |
| `JWT_SECRET`   | `CHANGE_ME_in_production_32_chars!!`                    | **Change this.** Signs session cookies.            |
| `DATABASE_URL` | `postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai` | asyncpg driver required                            |
| `REDIS_URL`    | `redis://localhost:6379`                                | Token recovery map                                 |
| `OLLAMA_URL`   | `http://localhost:11434`                                | Docker uses `http://host.docker.internal:11434`    |
| `OLLAMA_MODEL` | `tux-ai-chat`                                           | Global default; a dataset may override it          |
| `MODEL_PATH`   | `models/pii_model_v2`                                   | Falls back through `pii_model_advanced` → `pii_model_large` → `pii_model` → Presidio-only |
| `GRPC_PORT`    | `50051`                                                 |                                                    |

Rotating `MASTER_KEY` invalidates every stored dataset key — it needs a re-wrap migration, not a
config edit.

---

## Using it

### Datasets

A **dataset** scopes an encryption key, an optional dedicated chat model, and the RBAC grants over it.
Admins manage these under `/admin` in the UI, or over REST:

| Endpoint | What it does |
|----------|--------------|
| `POST /api/admin/datasets` | Create a dataset |
| `POST /api/admin/datasets/{id}/key` | Generate or set its AES key (wrapped with `MASTER_KEY`) |
| `POST /api/admin/datasets/{id}/import-rdb` · `/import-rdb-path` | Load a `dump.rdb` of pre-tokenized records so chat can resolve their tokens |
| `POST /api/admin/datasets/{id}/upload-model` · `/register-model-path` | Point this dataset at a specific GGUF / Ollama model |
| `POST /api/admin/rbac` | Grant a user access to an entity type within a dataset |
| `GET  /api/admin/users` · `POST` · `DELETE` | User management |

`scripts/get_tokens.sh` logs in and prints a JWT + CSRF pair ready to paste into `curl`, and can drive
the RDB-import and model-registration endpoints directly:

```bash
bash scripts/get_tokens.sh                          # tokens + dataset listing
bash scripts/get_tokens.sh --import-rdb <ds_id>
bash scripts/get_tokens.sh --register-model <ds_id>
```

A chat session with **no dataset** selected skips tokenization and decryption entirely — you are talking
to the raw model.

---

## PII detection library

Standalone of the web app, `src/` is a usable PII toolkit.

```bash
# Detect
python src/hybrid_detect.py --text "Contact John at john@email.com"

# Detect + AES-encrypt in place
python src/hybrid_detect.py --file document.txt --encrypt --output encrypted.txt

# Presidio only — no model load, much faster startup
python src/hybrid_detect.py --text "SSN: 123-45-6789" --no-ai

# Tokenize a .txt/.json file; recovery map goes to Redis
python src/tokenize_file.py --input data.txt --key "32ByteSecureKeyForAES256!!!!!!!"

# Reverse it
python src/decrypt_file.py --input data_tokenized.txt --session-id <id>

# Guided interactive menu (rich + questionary)
python src/cli.py
```

### Entity coverage

**Presidio built-ins** — `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `CRYPTO`, `IBAN_CODE`,
`IP_ADDRESS`, `NRP`, `LOCATION`, `US_BANK_NUMBER`, `US_DRIVER_LICENSE`, `US_ITIN`, `US_PASSPORT`, `US_SSN`,
`UK_NHS`, `MEDICAL_LICENSE`, `URL`

**Custom recognizers** ([src/recognizers.py](src/recognizers.py)) — `PROJECT_ID`, `PASSPORT_NUMBER`,
`DRIVERS_LICENSE`, `MEDICAL_RECORD_NUMBER`, `BANK_ACCOUNT`, `INSURANCE_NUMBER`, `EMPLOYEE_ID`,
`DATE_OF_BIRTH`, `TAX_ID`, `VIN`, `API_KEY`, `USERNAME`, `MAC_ADDRESS`, `SECURITY_BADGE`, `GRANT_NUMBER`,
`AWS_KEY`, `SERVICE_API_KEY`, `DB_CONNECTION`, `LICENSE_PLATE`, `PROFESSIONAL_LICENSE`, `CVV`,
`MEDICARE_NUMBER`, `PATENT_NUMBER`

**DistilBERT labels (BIO)** — `PER`, `ORG`, `LOC`, `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `DOB`, `LICENSE`,
`PASSPORT`, `IP_ADDRESS`, `MRN`, `BANK_ACCOUNT`, `USERNAME`, `VIN`, `API_KEY`, `MAC`, `EMP_ID`, `INSURANCE`

### Training the detector

```bash
# Verify the pipeline end-to-end in ~a minute
python src/train.py --smoke_test

# Full run — Faker-generated BIO-tagged data, 40% negative samples
python src/generate_data.py --count 100000 --output data/train_data_large.json
python src/train.py --data_file data/train_data_large.json --epochs 5 \
                    --output_dir models/pii_model_large
```

Apple Silicon MPS is detected and used automatically. 100K samples takes roughly 30–60 minutes.

Training data format — character offsets, converted to token-level BIO tags at load:

```json
{"text": "...", "entities": [[start, end, "LABEL"], ...]}
```

---

## LLM fine-tuning pipeline

Fine-tunes **Qwen3-8B** with 4-bit QLoRA (Unsloth) on tokenized documents, so the chat model is
structurally incapable of leaking PII it was never trained on. Needs a CUDA GPU with ≥16 GB VRAM —
use `--base-model unsloth/Qwen3-4B` for ~10 GB.

```bash
pip install -r requirements-llm.txt

# 1 · Synthetic documents across 5 persona types (Faker — all values fake)
python llm/generate_synthetic_docs.py --count 1000

# 2 · Tokenize, then overwrite and delete the raw originals (Redis must be up)
python llm/prepare_corpus.py

# 3 · Multi-turn chat dataset, 90/10 train/val
python llm/build_chat_dataset.py

# 4 · QLoRA fine-tune → adapter/ + merged_16bit/
python llm/train_qlora.py --train-file llm/data/chat/train.jsonl \
                          --val-file   llm/data/chat/val.jsonl

# 5 · Export GGUF + Modelfile, then run the printed `ollama create` command
python llm/export_to_gguf.py --merged-model-dir llm/checkpoints/run_001/merged_16bit/
```

Sanity run before committing GPU hours:

```bash
python llm/generate_synthetic_docs.py --count 20
python llm/prepare_corpus.py
python llm/build_chat_dataset.py --examples-per-doc 4
python llm/train_qlora.py --train-file llm/data/chat/train.jsonl \
                          --val-file llm/data/chat/val.jsonl --epochs 1
```

[llm/README.md](llm/README.md) covers OOM fallbacks, Qwen3 thinking mode (`/think`, `/no_think`), and
publishing to Hugging Face via `llm/upload_to_hf.py`.

### Retrieval (experimental)

[llm/build_rag_index.py](llm/build_rag_index.py) indexes tokenized records into ChromaDB, and
[api/services/rag.py](api/services/rag.py) implements a `retrieve()` over that collection.
**Neither is wired into the chat pipeline yet** — `retrieve()` has no callers. Also note that
`chromadb` and `sentence-transformers` are not in any requirements file; install them manually to
experiment.

---

## Security

Implemented:

- **Key hierarchy** — per-dataset AES keys, each wrapped with the server `MASTER_KEY` (AES-256-GCM)
  before storage. The database never holds an unwrapped key.
- **Tokenize-before-persist** — user messages are tokenized before the `INSERT`. Assistant messages are
  stored tokenized. Plaintext PII lives only in Redis, encrypted.
- **Least-privilege reads** — RBAC is checked per entity type per chunk; no grant means no decryption.
- **Audit trail** — every token resolution records user, token, entity type, dataset, and timestamp.
- **Passwords** — bcrypt.
- **Sessions** — JWT in HttpOnly cookies, 8-hour access token.
- **CSRF** — double-submit cookie enforced on all state-changing `/api` requests except `/login`.
- **Security headers** — `nosniff`, `X-Frame-Options: DENY`, strict referrer policy, and a CSP that
  restricts `connect-src` to self plus the Envoy origin.
- **Login rate limit** — 10/min via slowapi.
- **Input sanitization** — characters that could spoof `[LABEL_hexid]` token syntax are stripped from
  user input before tokenization.

Known gaps, if you are considering this for anything real:

- A refresh-token cookie is issued at login but there is no endpoint to exchange it — sessions simply
  expire after 8 hours.
- `CHAT_RATE_LIMIT` exists in config but is not enforced on the gRPC chat path.
- The seeded `admin@tux.ai / admin` account and the placeholder `MASTER_KEY` / `JWT_SECRET` defaults are
  development conveniences. All three must be changed.
- Redis holds the only copy of the token → plaintext mapping. See [todo.md](todo.md) for the
  persistence, TTL, connection-pooling, and Redis-auth work that is still outstanding.
- Default Postgres credentials in `docker-compose.yml` are `tuxai:tuxai`.

This is a research and demonstration project, not an audited product.

---

## Project structure

```
tux.ai/
├── api/                          # FastAPI (REST) + gRPC backend, one event loop
│   ├── main.py                   # App factory, CSRF + security middleware, gRPC lifecycle
│   ├── config.py                 # Pydantic settings ← .env.local
│   ├── models.py                 # SQLAlchemy ORM: User, Dataset, EncryptionKey,
│   │                             #   RbacGrant, ChatSession, Message, AuditLog
│   ├── security.py               # bcrypt, JWT, CSRF, AES-GCM master-key wrap/unwrap
│   ├── routers/                  # auth · admin · chats
│   ├── grpc/chat_servicer.py     # StreamChat: tokenize → Ollama → RBAC decrypt → audit
│   └── services/
│       ├── tokenizer.py          # Bridges the src/ detector into the API
│       ├── decryptor.py          # RBAC-aware token → plaintext resolution
│       ├── audit.py              # Decryption logging
│       ├── ollama.py             # Streaming client, strips Qwen3 <think> blocks
│       ├── redis_import.py       # dump.rdb → dataset token map
│       └── rag.py                # ChromaDB retriever (not yet wired in)
├── src/                          # Standalone PII detection / tokenization library
│   ├── hybrid_detect.py          # HybridDetector — Presidio + DistilBERT, span merge
│   ├── recognizers.py            # 23 custom PatternRecognizers (single source of truth)
│   ├── pseudonymize.py           # PIIPseudonymizer — tokens + recovery map
│   ├── utils.py                  # DetectionResult, merge_overlapping_spans, key validation
│   ├── tokenize_file.py          # Batch .txt/.json tokenizer
│   ├── decrypt_file.py           # Reverse a tokenized file via Redis
│   ├── redis_client.py           # Token map storage
│   ├── train.py                  # DistilBERT fine-tuning (HF Trainer, MPS-aware)
│   ├── generate_data.py          # Faker-based BIO-tagged training data
│   ├── inference.py              # Inference CLI
│   └── cli.py                    # Interactive menu (rich + questionary)
├── llm/                          # Qwen3 QLoRA pipeline (see llm/README.md)
├── frontend/                      # React 18 · TS · Tailwind 3 · Vite 5 · gRPC-Web
├── proto/chat.proto              # ChatService definition
├── envoy/                        # envoy.yaml (Docker) · envoy.local.yaml (native)
├── alembic/versions/             # 0001 schema + admin seed · 0002 dataset model fields
├── scripts/
│   ├── dev.sh                    # Local dev: containerized infra + native API/Vite
│   ├── pod.sh                    # Vast.ai / RunPod, fully native
│   ├── gen_proto.sh              # Python + TypeScript gRPC stubs
│   └── get_tokens.sh             # JWT/CSRF helper + admin operations
├── setup_chat.py                 # Download GGUF from HF, register with Ollama
├── docker-compose.yml
├── Dockerfile.api · Dockerfile.frontend
├── requirements.txt              # PII pipeline
├── requirements.api.txt          # API server
└── requirements-llm.txt          # QLoRA fine-tuning
```

> **Note:** `.gitignore` has a blanket `*.txt` rule, so `requirements.api.txt` is currently untracked.
> A fresh clone will not have it — `git add -f requirements.api.txt` before relying on the local-dev
> instructions above.

---

## Acknowledgments

- [Microsoft Presidio](https://github.com/microsoft/presidio) — rule-based PII detection and anonymization
- [Hugging Face Transformers](https://github.com/huggingface/transformers) — DistilBERT, Qwen3
- [Unsloth](https://github.com/unslothai/unsloth) — memory-efficient QLoRA
- [Ollama](https://ollama.com) — local LLM serving
- [Envoy](https://www.envoyproxy.io/) — gRPC-Web bridge
- [Faker](https://github.com/joke2k/faker) — synthetic data
