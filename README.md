# tux.ai

Privacy-preserving AI chat platform. PII is detected, tokenized, and never stored in plaintext — the chat model (Qwen3-8B via Ollama) works entirely on tokenized data. Authorized users can decrypt tokens on the fly through a role-based access control layer.

---

## Architecture

```
React (TypeScript + Tailwind)
  └─ REST (auth/admin)  →  FastAPI
  └─ gRPC-Web           →  Envoy  →  gRPC  →  FastAPI + gRPC servicer
                                                  ├─ PostgreSQL (sessions, RBAC, audit)
                                                  ├─ Redis (token recovery map)
                                                  └─ Ollama (tux-ai-chat)

PII pipeline (Python):  Presidio + fine-tuned DistilBERT → tokenizer → [LABEL_hexid]
LLM pipeline (Python):  synthetic docs → tokenize → QLoRA fine-tune → GGUF → Ollama
```

**Detection**: Hybrid rule-based (Presidio, 23+ custom recognizers) + contextual AI (fine-tuned DistilBERT token classifier). Spans are merged and deduplicated.

**Tokenization**: PII is replaced with `[LABEL_hexid]` placeholders. The original values are AES-encrypted and stored in Redis. The plaintext AES key is wrapped with a server `MASTER_KEY` (AES-256-GCM) and stored in Postgres — plaintext PII never touches the database.

**Chat**: The model is trained on tokenized text only. At chat time, authorized users' tokens are decrypted inline; unauthorized users see the placeholders.

**RBAC**: Per-user, per-dataset, per-entity-type grants. Admins get a wildcard grant automatically. Every decryption is written to an audit log.

---

## Services

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI | 8000 | REST API (auth, admin, chats) |
| gRPC | 50051 | Streaming chat service (internal) |
| Envoy | 8080 | gRPC-Web proxy for the browser |
| Frontend | 3000 | React SPA |
| Postgres | 5432 | Users, datasets, RBAC, sessions, audit |
| Redis | 6379 | Token → encrypted-value recovery map |
| Ollama | 11434 | LLM inference (`tux-ai-chat`) |

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- [Ollama](https://ollama.com) running locally (or uncomment the `ollama` service in `docker-compose.yml`)
- A trained `tux-ai-chat` Ollama model (see [LLM pipeline](#llm-fine-tuning-pipeline) below)
- A PII model in `models/` (see [PII model](#pii-detection-model) below, or use Presidio-only mode)

### 1. Configure environment

```bash
cp .env.example .env.local
# Edit .env.local — at minimum set MASTER_KEY and JWT_SECRET to random 32-char strings
```

### 2. Run setup script (first time only)

```bash
python setup_chat.py
```

This runs Alembic migrations, creates the first admin user, and seeds a default dataset.

### 3. Start all services

```bash
docker compose up --build
```

Frontend at `http://localhost:3000`. API docs at `http://localhost:8000/api/health`.

### Local development (without Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements.api.txt

# Start dependencies (Postgres, Redis, Ollama)
brew services start postgresql redis
ollama serve &

# Run migrations
alembic upgrade head

# Start API
uvicorn api.main:app --reload

# Start frontend
cd frontend && npm install && npm run dev
```

---

## PII Detection Model

### Supported entity types

**Presidio built-ins**: `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `CRYPTO`, `IBAN_CODE`, `IP_ADDRESS`, `NRP`, `LOCATION`, `US_BANK_NUMBER`, `US_DRIVER_LICENSE`, `US_ITIN`, `US_PASSPORT`, `US_SSN`, `UK_NHS`, `MEDICAL_LICENSE`, `URL`

**Custom recognizers** (`src/recognizers.py`): `PROJECT_ID`, `PASSPORT_NUMBER`, `DRIVERS_LICENSE`, `MEDICAL_RECORD_NUMBER`, `BANK_ACCOUNT`, `INSURANCE_NUMBER`, `EMPLOYEE_ID`, `DATE_OF_BIRTH`, `TAX_ID`, `VIN`, `API_KEY`, `USERNAME`, `MAC_ADDRESS`, `SECURITY_BADGE`, `GRANT_NUMBER`, `AWS_KEY`, `SERVICE_API_KEY`, `DB_CONNECTION`, `LICENSE_PLATE`, `PROFESSIONAL_LICENSE`, `CVV`, `MEDICARE_NUMBER`, `PATENT_NUMBER`

**AI model labels**: `PER`, `ORG`, `LOC`, `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `DOB`, `LICENSE`, `PASSPORT`, `IP_ADDRESS`, `MRN`, `BANK_ACCOUNT`, `USERNAME`, `VIN`, `API_KEY`, `MAC`, `EMP_ID`, `INSURANCE`

### Train from scratch

```bash
# Generate training data
python src/generate_data.py --count 100000 --output data/train_data_large.json

# Train (Apple Silicon uses MPS automatically; ~30-60 min for 100K samples)
python src/train.py --data_file data/train_data_large.json --epochs 5 --output_dir models/pii_model_large

# Smoke test
python src/train.py --smoke_test
```

### CLI usage

```bash
# Detect PII
python src/hybrid_detect.py --text "Contact John at john@email.com"

# Detect and AES-encrypt
python src/hybrid_detect.py --file document.txt --encrypt --output encrypted.txt

# Presidio-only (no AI model, faster)
python src/hybrid_detect.py --text "SSN: 123-45-6789" --no-ai

# Tokenize a file (PII → [LABEL_hexid], recovery map in Redis)
python src/tokenize_file.py --input data.txt --key "32ByteSecureKeyForAES256!!!!!!!"
```

---

## LLM Fine-Tuning Pipeline

Fine-tunes **Qwen3-8B** (QLoRA, 4-bit) on tokenized PII data so the chat model never sees raw PII. Requires a CUDA GPU with ≥16 GB VRAM (or use `--base-model unsloth/Qwen3-4B` for ~10 GB).

```bash
pip install -r requirements-llm.txt
```

### Five-step pipeline

```bash
# 1. Generate synthetic documents (Faker, 5 persona types)
python llm/generate_synthetic_docs.py --count 1000

# 2. Tokenize docs, securely wipe raw originals (Redis must be running)
python llm/prepare_corpus.py

# 3. Build multi-turn chat dataset (90/10 train/val split)
python llm/build_chat_dataset.py

# 4. Fine-tune (saves adapter + merged 16-bit weights)
python llm/train_qlora.py \
    --train-file llm/data/chat/train.jsonl \
    --val-file   llm/data/chat/val.jsonl

# 5. Export to GGUF and register with Ollama
python llm/export_to_gguf.py \
    --merged-model-dir llm/checkpoints/run_001/merged_16bit/
# Follow the printed `ollama create` commands
```

Quick sanity run (before scaling up):
```bash
python llm/generate_synthetic_docs.py --count 20
python llm/prepare_corpus.py
python llm/build_chat_dataset.py --examples-per-doc 4
python llm/train_qlora.py --train-file llm/data/chat/train.jsonl --val-file llm/data/chat/val.jsonl --epochs 1
```

See [llm/README.md](llm/README.md) for hardware fallback, Qwen3 thinking mode, and upload to HuggingFace.

---

## Security Notes

- **MASTER_KEY** encrypts all dataset AES keys at rest (AES-256-GCM). Rotate it only with a migration.
- **JWT_SECRET** signs access (8h) and refresh (7d) tokens.
- **CSRF** double-submit cookie on all state-changing REST endpoints.
- **Messages** are stored tokenized — plaintext PII never reaches Postgres.
- **Audit log** records every token decryption (user, token, dataset, timestamp).
- **Rate limiting**: 10 req/min on `/login`, 30 req/min on chat endpoints.

---

## Project Structure

```
tux.ai/
├── api/                   # FastAPI + gRPC backend
│   ├── main.py            # App factory, middleware, gRPC lifecycle
│   ├── models.py          # SQLAlchemy ORM (User, Dataset, RBAC, Chat, Audit)
│   ├── security.py        # bcrypt, JWT, CSRF, AES-GCM master-key wrap/unwrap
│   ├── config.py          # Pydantic settings (.env.local)
│   ├── routers/           # auth, admin, chats
│   └── grpc/              # gRPC servicer (streaming chat)
├── frontend/              # React 18 + TypeScript + Tailwind + gRPC-Web
├── proto/chat.proto        # ChatService protobuf definition
├── envoy/                 # Envoy gRPC-Web proxy config
├── llm/                   # Qwen3-8B fine-tuning pipeline
│   ├── generate_synthetic_docs.py
│   ├── prepare_corpus.py
│   ├── build_chat_dataset.py
│   ├── train_qlora.py
│   └── export_to_gguf.py
├── src/                   # PII detection / tokenization library
│   ├── hybrid_detect.py   # HybridDetector (Presidio + DistilBERT)
│   ├── recognizers.py     # 23 custom PatternRecognizers
│   ├── pseudonymize.py    # PIIPseudonymizer (token → recovery map)
│   ├── tokenize_file.py   # Batch file processor
│   ├── train.py           # DistilBERT fine-tuning
│   └── generate_data.py   # BIO-tagged synthetic training data
├── alembic/               # DB migrations
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.frontend
├── requirements.txt       # PII pipeline deps
├── requirements.api.txt   # API server deps
├── requirements-llm.txt   # LLM fine-tuning deps
└── .env.example
```

---

## Acknowledgments

- [Microsoft Presidio](https://github.com/microsoft/presidio) — rule-based PII detection
- [Hugging Face Transformers](https://github.com/huggingface/transformers) — DistilBERT + Qwen3
- [Unsloth](https://github.com/unslothai/unsloth) — QLoRA fine-tuning
- [Ollama](https://ollama.com) — local LLM inference
- [Faker](https://github.com/joke2k/faker) — synthetic data generation
