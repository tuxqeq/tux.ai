# 🔐 tux.ai - Hybrid PII Detection & Encryption System

Advanced AI-powered system for detecting and encrypting Personally Identifiable Information (PII) using a hybrid approach combining:
- **AI Model**: Fine-tuned transformer for contextual PII detection
- **Presidio**: Rule-based pattern matching for structured data (SSN, credit cards, emails, etc.)

## 🚀 Features

- **12+ PII Types**: Names, emails, phones, SSN, credit cards, addresses, DOB, passports, IPs, medical records, bank accounts, usernames
- **Hybrid Detection**: Combines AI contextual understanding with regex pattern matching
- **AES Encryption**: Reversible encryption of detected PII
- **High Accuracy**: Trained on 100K+ samples with 40% negative examples to reduce false positives
- **Customizable**: Adjustable AI confidence thresholds, Presidio-only mode, custom encryption keys

---

## 📋 Prerequisites

- Python 3.11+
- macOS, Linux, or Windows
- 8GB+ RAM recommended for training

---

## ⚙️ Installation

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd tux.ai
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Download Spacy Language Model
```bash
python -m spacy download en_core_web_lg
```

---

## 🎯 Quick Start

### Option 1: Use Pre-trained Models (Fast)

If you have trained models in `models/`, skip to usage:

```bash
# Detect PII only
python src/hybrid_detect.py --text "Contact John Doe at john@email.com or 555-1234"

# Detect and encrypt PII
python src/hybrid_detect.py --text "SSN: 123-45-6789" --encrypt

# Process a file
python src/hybrid_detect.py --file document.txt --encrypt --output encrypted.txt
```

### Option 2: Train From Scratch

#### Step 1: Generate Training Data
```bash
# Generate 100,000 training samples (recommended for production)
python src/generate_data.py --count 100000 --output data/train_data_large.json

# Or generate smaller dataset for testing
python src/generate_data.py --count 10000 --output data/train_data_test.json
```

#### Step 2: Train the Model
```bash
# Full training (recommended)
python src/train.py --data_file data/train_data_large.json --epochs 5 --output_dir models/pii_model_large

# Quick training for testing
python src/train.py --data_file data/train_data_test.json --epochs 3 --output_dir models/pii_model_test

# Smoke test (minimal training)
python src/train.py --smoke_test
```

**Training Notes:**
- On Apple Silicon (M1/M2/M3): Uses MPS GPU acceleration automatically
- 100K samples takes ~30-60 minutes on modern hardware
- Models saved in `models/` directory with checkpoints

#### Step 3: Test Detection
```bash
python src/hybrid_detect.py --model_path models/pii_model_large --text "Patient Jane Smith, DOB 01/15/1990, SSN 987-65-4321"
```

---

## 📖 Usage Guide

### Detection Only

**Interactive mode:**
```bash
python src/hybrid_detect.py
# Enter text when prompted, type 'exit' to quit
```

**Single text analysis:**
```bash
python src/hybrid_detect.py --text "Email me at alice@company.com"
```

**File analysis:**
```bash
python src/hybrid_detect.py --file sensitive_data.txt
```

### Detection + Encryption

**Encrypt text:**
```bash
python src/hybrid_detect.py --text "Credit card: 4532-1234-5678-9010" --encrypt
```

**Encrypt file:**
```bash
python src/hybrid_detect.py --file data.txt --encrypt --output encrypted_data.txt
```

**Custom encryption key:**
```bash
python src/hybrid_detect.py --file data.txt --encrypt --key "MySecure16ByteKey"
# Key must be 16, 24, or 32 bytes
```

### Advanced Options

**Presidio-only mode** (no AI, faster, fewer false positives):
```bash
python src/hybrid_detect.py --file data.txt --encrypt --no-ai
```

**Adjust AI confidence threshold** (default: 0.95):
```bash
python src/hybrid_detect.py --text "Data here" --ai-threshold 0.99
# Higher = fewer detections but more accurate
```

**Use different model:**
```bash
python src/hybrid_detect.py --model_path models/pii_model_advanced --text "Test data"
```

---

## 🏗️ Project Structure

```
tux.ai/
├── data/                          # Training datasets
│   ├── train_data.json           # Small dataset
│   ├── train_data_advanced.json  # Medium dataset
│   ├── train_data_full.json      # Large dataset
│   └── train_data_large.json     # 100K samples (generated)
├── models/                        # Trained models
│   ├── pii_model/                # Base model
│   ├── pii_model_advanced/       # Intermediate model
│   ├── pii_model_full/           # Full model
│   └── pii_model_large/          # Production model (100K samples)
├── src/                           # Source code
│   ├── generate_data.py          # Synthetic data generator
│   ├── train.py                  # Model training pipeline
│   ├── inference.py              # Simple inference (AI only)
│   └── hybrid_detect.py          # Hybrid detection + encryption
├── notebooks/                     # Jupyter experiments
├── encrypt_pii.py                # Presidio-only encryption (legacy)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── .gitignore                    # Git ignore rules
```

---

## 🧪 Training Data Details

### Generated Data Includes:
- **Names (PER)**: Contextual person names
- **Emails (EMAIL)**: Standard email addresses
- **Phones (PHONE)**: Various phone formats
- **SSN (SSN)**: Social Security Numbers
- **Credit Cards (CREDIT_CARD)**: Card numbers
- **Addresses (LOC)**: Physical addresses
- **Organizations (ORG)**: Company names
- **DOB (DOB)**: Dates of birth
- **Licenses (LICENSE)**: Driver licenses
- **Passports (PASSPORT)**: Passport numbers
- **IPs (IP_ADDRESS)**: IP addresses
- **Medical Records (MRN)**: Medical record numbers
- **Bank Accounts (BANK_ACCOUNT)**: Account numbers
- **Usernames (USERNAME)**: User login names

### Negative Examples (40%):
Sentences without PII to prevent false positives:
- "The company is doing well."
- "Personal information should be protected."
- "Contact information has been updated."
- 60+ variations to teach context

---

## 🔧 Configuration

### Training Parameters

Edit in `src/train.py` or pass as arguments:
- `--epochs`: Number of training iterations (default: 3, recommended: 5)
- `--data_file`: Path to training data JSON
- `--output_dir`: Where to save trained model
- `--smoke_test`: Quick test with minimal data

### Detection Parameters

- `--model_path`: Path to AI model (default: `models/pii_model_advanced`)
- `--no-ai`: Disable AI, use Presidio only
- `--ai-threshold`: Confidence threshold (0.0-1.0, default: 0.95)
- `--encrypt`: Enable encryption
- `--key`: AES encryption key (16/24/32 bytes)
- `--output`: Output file path

---

## 📊 Performance

### Model Metrics
- **Precision**: High (specific entity types, negative samples reduce false positives)
- **Recall**: High (hybrid approach catches both contextual and pattern-based PII)
- **Speed**: ~1000 tokens/sec on Apple M1

### Presidio Coverage
- Email, Phone, SSN, Credit Cards, IPs, URLs
- Dates, Locations, Person Names, Organizations
- Medical licenses, Bank accounts, Passports

---

## 🛠️ Troubleshooting

### Model Over-detecting (encrypting normal words)
**Solution**: Use Presidio-only mode or increase AI threshold
```bash
python src/hybrid_detect.py --file data.txt --no-ai --encrypt
# OR
python src/hybrid_detect.py --file data.txt --ai-threshold 0.99 --encrypt
```

### Training Warnings (MPS pin_memory)
**Safe to ignore** - Apple Silicon GPU acceleration works despite warning

### Out of Memory During Training
**Solution**: Reduce batch size in `src/train.py` or use smaller dataset

### Presidio Not Detecting SSN/Credit Cards
**Solution**: Ensure Spacy model is installed
```bash
python -m spacy download en_core_web_lg
```

---

## 🤝 Contributing

1. Generate better training data with `src/generate_data.py`
2. Add new PII types in templates
3. Improve hybrid detection logic in `src/hybrid_detect.py`
4. Submit pull requests!

---

## 📄 License

[Your License Here]

---

## 🙏 Acknowledgments

- **Hugging Face Transformers**: Model architecture
- **Microsoft Presidio**: Rule-based PII detection
- **Spacy**: NLP models
- **Faker**: Synthetic data generation

---

**Built with ❤️ for data privacy and security**
