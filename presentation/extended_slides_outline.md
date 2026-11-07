# Extended Presentation — Step-by-Step Plan

**How to read this document.** Each slide block has three parts:

- **ON SLIDE** — the exact text to put on the slide.
- **VISUAL** — which diagram (from `presentation/diagrams/`) belongs on this slide, or a layout note.
- **SAY** — what to say out loud. Don't read the slide; expand on it.

**Style to match the original deck:**

- Bold serif title in the top-left, with the short black bar above it.
- Body text on the right, with the small 8-point-star bullets, or two-column layouts.
- Light gray background, black ink, no color.
- Page number in the bottom right.

**Narrative arc:** introduce the system → walk through it as a pipeline → demo it.

---

## Slide 9 — *From Concept to System* — 0:30

**ON SLIDE**

> Title: **From Concept to System**
>
> Subtitle: *What's been built since January*
>
> Body (one centered paragraph):
> The architecture from the first presentation was a sketch. Over the last months it became a working, multi-service application — every component you are about to see is implemented and runs locally.

**VISUAL** — text-only slide. Keep it sparse.

**SAY** — "What I want to do today is walk you through the system as a pipeline — the same path a piece of data takes when it enters the system. We'll cover detection, tokenization, training, decryption, and then I'll show the whole thing end-to-end. The last two minutes will be a live demo."

---

## Slide 10 — *The Pipeline* — 0:45

**ON SLIDE**

> Title: **The Pipeline**
>
> Subtitle: *Five stages, in order*

Body (5 numbered items, right-aligned, one line each):

> 1. **Detect** — find the PII
> 2. **Tokenize** — replace and encrypt it
> 3. **Train** — fine-tune the LLM on tokens only
> 4. **Decrypt** — release plaintext per user role
> 5. **Serve** — chat over the whole flow

**VISUAL** — five small numbered boxes left-to-right (you can sketch this as five rounded rectangles connected by arrows; matches the System Architecture slide's style).

**SAY** — "Five stages. Each stage on its own is a known technique; the contribution of this thesis is putting them together so that no single stage ever has access to both raw data and the model. We'll go one at a time."

---

# Step 1 — Detection

## Slide 11 — *Step 1 · Detection* — 1:30

**ON SLIDE**

> Title: **Detection**
>
> Subtitle: *Finding PII before anything else can*
>
> Body (3 bullets, right-aligned):
>
> — **Layer 1 — Presidio (rules).** 17 built-in entity types plus 23 custom regex recognizers for API keys, medical record numbers, badges, license plates, and more.
>
> — **Layer 2 — DistilBERT (AI).** A transformer fine-tuned on 100,000 BIO-tagged synthetic samples; it catches contextual PII that rigid patterns miss — informal names, foreign phone formats, organizational references.
>
> — **Merge.** Both layers run in parallel. Overlapping spans are deduplicated; either source may contribute to the final result.

**VISUAL** — `diagram_detection_pipeline.svg`

**SAY** — "Detection has to be the strongest link in the chain, because if something slips past, everything downstream is compromised. So I don't trust a single method. Layer one is Presidio — Microsoft's open-source PII engine — extended with twenty-three custom regex recognizers I wrote for domain-specific identifiers. Layer two is a DistilBERT model I fine-tuned on a hundred thousand synthetic samples; it learns what a name *looks like in context*, even when the format is unusual. The two run in parallel and the spans are merged."

---

# Step 2 — Tokenization

## Slide 12 — *Step 2 · Tokenization* — 1:30

**ON SLIDE**

> Title: **Tokenization**
>
> Subtitle: *From `John Smith` to `[PERSON_a1b2]`*
>
> Body (3 bullets, right-aligned):
>
> — Each detected span is replaced with a short placeholder of the form `[LABEL_hexid]`. The label tells the model *what kind of thing* it is; the hex ID tells it *which one*.
>
> — The original value is encrypted with AES-256 using a per-dataset key and stored in Redis as a token → ciphertext map.
>
> — The per-dataset key itself is wrapped with a server `MASTER_KEY` using AES-256-GCM and stored in PostgreSQL. Plaintext PII never reaches the database.

**VISUAL** — `diagram_tokenization.svg`

**SAY** — "Once we know where the PII is, we replace it. Every span becomes a placeholder like `[PERSON_a1b2]`. The label is preserved so the model can still reason about the *type* of entity — that's a person, that's a phone number — but the actual value is gone. The real value is AES-encrypted and stored in Redis. And critically, the AES key itself is encrypted with a master key. So even if an attacker dumps the database, they have a ciphertext and an encrypted key — nothing usable."

---

# Step 3 — Training

## Slide 13 — *Step 3 · Training the Model* — 1:30

**ON SLIDE**

> Title: **Training**
>
> Subtitle: *A chat model that never saw real PII*
>
> Body (3 bullets, right-aligned):
>
> — **Synthetic corpus.** 1,000+ documents across 5 personas — banking, healthcare, government contractor, tech startup, international business — generated with Faker. Every value is fake by construction.
>
> — **Tokenize, then wipe.** Each document is run through the same detection engine and pseudonymized. The raw originals are then overwritten and securely deleted from disk.
>
> — **QLoRA fine-tune of Qwen3-8B.** The model is trained on tokenized text only. It learns the shape of a conversation about `[PERSON_a1b2]`, `[SSN_c3d4]`, `[BANK_e5f6]` — never the values themselves.

**VISUAL** — `diagram_llm_pipeline.svg`

**SAY** — "Most privacy methods — differential privacy, federated learning — let the model see real data at some point. The contribution here is that the model is *never* exposed to real PII, not even during training. I generate the training corpus from scratch with Faker, run it through the same tokenization pipeline, and then securely wipe the raw files. The model that comes out the other end is mathematically incapable of leaking PII it never received."

---

# Step 4 — Decryption

## Slide 14 — *Step 4 · Decryption & Access* — 1:30

**ON SLIDE**

> Title: **Decryption**
>
> Subtitle: *One model, many views*
>
> Two columns.
>
> **Left — three roles:**
>
> — **Admin** — every token decrypted in place (wildcard grant).
> — **Analyst** — only the entity types granted to them (e.g. `PERSON`, `EMAIL`).
> — **Viewer** — sees only `[LABEL_hexid]` placeholders.
>
> **Right — guarantees:**
>
> — Decryption happens on the way *out*, per streamed chunk, against the live RBAC table.
> — Every decryption is written to a Postgres audit log: token, user, dataset, timestamp.
> — Revoking a grant takes effect on the next chunk — no model re-run needed.

**VISUAL** — small role-vs-grant table, or just two clean columns. Optionally a tiny inline example: `"Patient [PERSON_a1b2]..."` → admin sees `"Patient Alice..."`, viewer keeps the token.

**SAY** — "The original deck called this the 'access control layer' — this is what it actually does. The model always returns tokenized text. On the way back to the user, a decryptor walks each token, checks the user's role against their grants, and either substitutes the plaintext or leaves the placeholder. That means the *same* conversation can show different content to different users without ever re-running the model — and every plaintext reveal is recorded."

---

# Step 5 — The Whole System

## Slide 15 — *Step 5 · End-to-End* — 1:30

**ON SLIDE**

> Title: **End-to-End**
>
> Subtitle: *A prompt's life, from keystroke to display*
>
> Body (numbered, right-aligned):
>
> 1. User submits a prompt over gRPC-Web; JWT authenticates the request.
> 2. Backend runs detection + tokenization on the prompt. The LLM only ever receives placeholders.
> 3. Qwen3-8B (served by Ollama) streams its reply — also in tokens.
> 4. Each chunk passes through the RBAC decryptor, is audit-logged, and is sent to the browser.
> 5. The tokenized message is persisted to Postgres. Plaintext never touches storage.

**VISUAL** — `diagram_runtime_flow.svg`

**SAY** — "Now putting all of it together. The browser sends a prompt. The backend tokenizes before anything else — Ollama, the LLM runtime, has no idea what the conversation is really about. It streams its reply. Each chunk passes through the decryptor, which substitutes plaintext for users who are allowed to see it. The message stored in the database is always the tokenized version. The plaintext is reconstructed on the fly, per user, every time."

---

## Slide 16 — *Stack & Scale* — 1:00

**ON SLIDE**

> Title: **Stack & Scale**
>
> Two columns.
>
> **Left — Stack:**
>
> — Backend: Python · FastAPI · gRPC · SQLAlchemy
> — LLM: Qwen3-8B · Unsloth/QLoRA · Ollama
> — Detector: DistilBERT · HuggingFace · Presidio
> — Data: PostgreSQL · Redis · Envoy
> — Frontend: React · TypeScript · Tailwind · gRPC-Web
> — Crypto: AES-256-GCM · bcrypt · JWT
>
> **Right — Scale:**
>
> — 23 custom recognizers
> — 19 AI entity labels
> — 100,000 detector training samples
> — 1,000+ LLM training documents
> — ~6,000 lines of Python, ~1,400 of TypeScript
> — 7 services, all local, orchestrated via Docker Compose

**VISUAL** — text-only, two clean columns.

**SAY** — "Quickly, to put scale on it. Everything runs locally — no cloud APIs, no third-party inference. Seven services in Docker Compose. The two key numbers: a hundred thousand synthetic samples to train the detector, and a thousand multi-persona documents to train the chat model on."

---

# Demo

## Slide 17 — *Live Demo* — 2:00

**ON SLIDE**

> Title: **Demo**
>
> Centered, large: **Live Demo**
>
> Small text below:
> *Login → send a prompt with PII → view it as a viewer → switch to admin → check the audit log*

**VISUAL** — minimal text-only slide. Keep audience focus on the screen, not the slide.

**SAY** — Walk through the demo in this order:

1. Log in as **viewer**. Send a prompt with PII: *"Process the record for John Smith, DOB 03/14/1985, MRN-784512."*
2. Point out the badges in the chat history — `[PERSON_xxxx]`, `[DOB_xxxx]`, `[MRN_xxxx]`. The model still produces a coherent answer.
3. Open Postgres in a side window. Show that `messages.content` contains only tokens.
4. Switch to **admin**. Reopen the same chat session. Names and dates appear in plaintext now — without re-running the model.
5. Open the audit log. Show that the decryptions were recorded.

If the demo fails, advance to Slide 18.

---

## Slide 18 — *Demo · Screenshots (Backup)* — skip if live demo worked

**ON SLIDE**

> No title — full-bleed 2×2 image grid:
>
> 1. Login screen
> 2. Chat view as **viewer** — tokens visible
> 3. Same chat view as **admin** — plaintext
> 4. Audit log table

**VISUAL** — screenshot collage. Use the screenshots from your repo.

**SAY** — only used if the live demo had problems. "Here's the same flow captured — viewer sees tokens, admin sees plaintext, audit log records every reveal."

---

## Timing summary

| # | Slide                  | Time     |
| - | ---------------------- | -------- |
| 9 | From Concept to System | 0:30     |
| 10 | The Pipeline          | 0:45     |
| 11 | Step 1 · Detection    | 1:30     |
| 12 | Step 2 · Tokenization | 1:30     |
| 13 | Step 3 · Training     | 1:30     |
| 14 | Step 4 · Decryption   | 1:30     |
| 15 | Step 5 · End-to-End   | 1:30     |
| 16 | Stack & Scale         | 1:00     |
| 17 | Live Demo             | 2:00     |
|   | **Total**             | **11:45** |

If you need to land exactly at 10:00: merge slides 9 and 10 into a single intro (saves ~1:00) and trim Slide 16 to a 30-second name-drop instead of a full read-through.

---

## Diagrams (saved as separate SVG files)

In `presentation/diagrams/`, ready to drop into your slide tool:

- `diagram_detection_pipeline.svg` — Slide 11
- `diagram_tokenization.svg` — Slide 12
- `diagram_llm_pipeline.svg` — Slide 13
- `diagram_runtime_flow.svg` — Slide 15
