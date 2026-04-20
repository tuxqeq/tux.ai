# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**tux.ai** is a hybrid PII (Personally Identifiable Information) detection and encryption system that combines Microsoft Presidio (rule-based) with a fine-tuned DistilBERT transformer model (AI-based) for contextual detection. Detected PII can be AES-encrypted or replaced with readable tokens with an encrypted recovery map.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Common Commands

```bash
# Detect PII in text
python src/hybrid_detect.py --text "Contact John at john@email.com"

# Detect and encrypt
python src/hybrid_detect.py --file document.txt --encrypt --output encrypted.txt

# Presidio-only (faster, no AI model loading)
python src/hybrid_detect.py --text "SSN: 123-45-6789" --no-ai

# Tokenize a file (replaces PII with [LABEL_hexid] tokens)
python src/tokenize_file.py --input data.txt --key "32ByteSecureKeyForAES256!!!!!!!"

# Interactive mode
python src/hybrid_detect.py

# Generate synthetic training data
python src/generate_data.py --count 100000 --output data/train_data_large.json

# Train model
python src/train.py --data_file data/train_data_large.json --epochs 5 --output_dir models/pii_model_large

# Smoke test (quick training validation)
python src/train.py --smoke_test
```

## Architecture

### Detection Pipeline
1. **Presidio** (rule-based): Detects structured PII — emails, phones, SSN, credit cards, IPs, and 23 custom entity types
2. **AI model** (token classification): Fine-tuned DistilBERT detects contextual PII
3. **Merge**: Overlapping spans are deduplicated; both sources may contribute to a result

### Key Files
- `src/recognizers.py` — All 23 custom Presidio `PatternRecognizer` definitions (single source of truth)
- `src/utils.py` — Shared utilities: `DetectionResult` TypedDict, `merge_overlapping_spans()`, `validate_aes_key()`
- `src/hybrid_detect.py` — Core `HybridDetector` class; CLI entry point for detection/encryption
- `src/pseudonymize.py` — `PIIPseudonymizer` class; replaces PII with tokens and maintains recovery map
- `src/tokenize_file.py` — Batch processor for `.txt` / `.json` files using pseudonymizer
- `src/train.py` — Fine-tunes DistilBERT using HF `Trainer` API; supports Apple Silicon MPS
- `src/generate_data.py` — Generates BIO-tagged training data using Faker templates (40% negative samples)
- `src/inference.py` — CLI inference using `HybridDetector`

### Models
- `models/pii_model_advanced/` — Default model used by `hybrid_detect.py`
- `models/pii_model_large/` — Production model trained on 100K samples
- Models are excluded from git (see `.gitignore`)
- Run `python src/train.py --smoke_test` to verify training pipeline before a full run

### Data Format
Training data uses JSON with character-offset entity spans:
```json
{"text": "...", "entities": [[start, end, "LABEL"], ...]}
```
These are converted to token-level BIO tags during training.

### Encryption
- AES encryption via Presidio's `AnonymizerEngine` with `OperatorConfig("encrypt", ...)`
- Keys must be 16, 24, or 32 bytes
- Tokenization produces `[LABEL_hexid]` placeholders with a JSON recovery map

## Supported PII Types

Presidio built-ins: `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `CRYPTO`, `IBAN_CODE`, `IP_ADDRESS`, `NRP`, `LOCATION`, `US_BANK_NUMBER`, `US_DRIVER_LICENSE`, `US_ITIN`, `US_PASSPORT`, `US_SSN`, `UK_NHS`, `MEDICAL_LICENSE`, `URL`

Custom recognizers (in `src/recognizers.py`): `PROJECT_ID`, `PASSPORT_NUMBER`, `DRIVERS_LICENSE`, `MEDICAL_RECORD_NUMBER`, `BANK_ACCOUNT`, `INSURANCE_NUMBER`, `EMPLOYEE_ID`, `DATE_OF_BIRTH`, `TAX_ID`, `VIN`, `API_KEY`, `USERNAME`, `MAC_ADDRESS`, `SECURITY_BADGE`, `GRANT_NUMBER`, `AWS_KEY`, `SERVICE_API_KEY`, `DB_CONNECTION`, `LICENSE_PLATE`, `PROFESSIONAL_LICENSE`, `CVV`, `MEDICARE_NUMBER`, `PATENT_NUMBER`

AI model labels (BIO): `PER`, `ORG`, `LOC`, `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `DOB`, `LICENSE`, `PASSPORT`, `IP_ADDRESS`, `MRN`, `BANK_ACCOUNT`, `USERNAME`, `VIN`, `API_KEY`, `MAC`, `EMP_ID`, `INSURANCE`
