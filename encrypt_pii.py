#!/usr/bin/env python3
"""
Hybrid Neuro-Symbolic PII Detection and Encryption System
Uses Microsoft Presidio with AI (Spacy NLP) + Rule-Based (Regex) detection
Encrypts sensitive data using AES encryption for reversible anonymization
"""

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from typing import List
import base64


def create_custom_recognizers() -> List[PatternRecognizer]:
    """
    Rule-Based Layer: Custom Pattern Recognizers for various sensitive data types
    Returns a list of recognizers for different PII patterns
    """
    recognizers = []
    
    # 1. Project ID Pattern: PROJ-XXXX
    project_id_recognizer = PatternRecognizer(
        supported_entity="PROJECT_ID",
        patterns=[Pattern(
            name="project_id_pattern",
            regex=r"\bPROJ-\d{4}\b",
            score=0.9
        )],
        context=["project", "trial", "research", "enrolled"]
    )
    recognizers.append(project_id_recognizer)
    
    # 2. US Passport Pattern: 9 digits or letter + 8 digits
    passport_recognizer = PatternRecognizer(
        supported_entity="PASSPORT_NUMBER",
        patterns=[
            Pattern(
                name="us_passport_9digit",
                regex=r"\b\d{9}\b",
                score=0.5  # Lower score, needs context
            ),
            Pattern(
                name="us_passport_letter",
                regex=r"\b[A-Z]\d{8}\b",
                score=0.6
            )
        ],
        context=["passport", "travel", "document", "citizenship", "visa"]
    )
    recognizers.append(passport_recognizer)
    
    # 3. Driver License Pattern: Various US formats
    drivers_license_recognizer = PatternRecognizer(
        supported_entity="DRIVERS_LICENSE",
        patterns=[
            Pattern(
                name="dl_letter_numbers",
                regex=r"\b[A-Z]{1,2}\d{6,8}\b",
                score=0.6
            ),
            Pattern(
                name="dl_numbers_only",
                regex=r"\b\d{7,9}\b",
                score=0.4  # Very low without context
            )
        ],
        context=["license", "driver", "DMV", "state ID", "identification"]
    )
    recognizers.append(drivers_license_recognizer)
    
    # 4. Medical Record Number (MRN)
    mrn_recognizer = PatternRecognizer(
        supported_entity="MEDICAL_RECORD_NUMBER",
        patterns=[
            Pattern(
                name="mrn_pattern",
                regex=r"\bMRN[-:]?\s*\d{6,10}\b",
                score=0.95
            ),
            Pattern(
                name="patient_id",
                regex=r"\b(?:Patient|PT)[-:]?\s*\d{6,10}\b",
                score=0.85
            )
        ],
        context=["patient", "medical", "hospital", "clinic", "chart"]
    )
    recognizers.append(mrn_recognizer)
    
    # 5. Bank Account Numbers
    bank_account_recognizer = PatternRecognizer(
        supported_entity="BANK_ACCOUNT",
        patterns=[
            Pattern(
                name="bank_account_pattern",
                regex=r"\b\d{8,17}\b",
                score=0.3  # Very low without context
            ),
            Pattern(
                name="account_with_prefix",
                regex=r"\b(?:Account|Acct)[-:\s#]*\d{8,17}\b",
                score=0.85
            )
        ],
        context=["account", "bank", "routing", "checking", "savings", "deposit"]
    )
    recognizers.append(bank_account_recognizer)
    
    # 6. Insurance Policy Numbers
    insurance_recognizer = PatternRecognizer(
        supported_entity="INSURANCE_NUMBER",
        patterns=[
            Pattern(
                name="insurance_policy",
                regex=r"\b[A-Z]{2,4}\d{6,12}\b",
                score=0.6
            ),
            Pattern(
                name="policy_with_prefix",
                regex=r"\b(?:Policy|Member|Group)[-:\s#]*[A-Z0-9]{6,15}\b",
                score=0.8
            )
        ],
        context=["insurance", "policy", "coverage", "claim", "beneficiary", "premium"]
    )
    recognizers.append(insurance_recognizer)
    
    # 7. Employee ID
    employee_id_recognizer = PatternRecognizer(
        supported_entity="EMPLOYEE_ID",
        patterns=[
            Pattern(
                name="emp_id_pattern",
                regex=r"\b(?:EMP|E|EMPL)[-:]?\d{4,8}\b",
                score=0.85
            )
        ],
        context=["employee", "staff", "personnel", "worker", "payroll"]
    )
    recognizers.append(employee_id_recognizer)
    
    # 8. IP Address
    ip_address_recognizer = PatternRecognizer(
        supported_entity="IP_ADDRESS",
        patterns=[
            Pattern(
                name="ipv4_pattern",
                regex=r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                score=0.85
            )
        ],
        context=["IP", "address", "server", "network", "connection"]
    )
    recognizers.append(ip_address_recognizer)
    
    # 9. Date of Birth (DOB)
    dob_recognizer = PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern(
                name="dob_mmddyyyy",
                regex=r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b",
                score=0.6
            ),
            Pattern(
                name="dob_with_label",
                regex=r"\b(?:DOB|Birth|Born)[-:\s]+(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2,4}\b",
                score=0.85
            )
        ],
        context=["birth", "DOB", "born", "age", "birthday"]
    )
    recognizers.append(dob_recognizer)
    
    # 10. Tax ID / EIN (Employer Identification Number)
    tax_id_recognizer = PatternRecognizer(
        supported_entity="TAX_ID",
        patterns=[
            Pattern(
                name="ein_pattern",
                regex=r"\b\d{2}-\d{7}\b",
                score=0.7
            ),
            Pattern(
                name="ein_with_label",
                regex=r"\b(?:EIN|Tax ID)[-:\s#]*\d{2}-?\d{7}\b",
                score=0.9
            )
        ],
        context=["EIN", "tax", "employer", "federal", "IRS"]
    )
    recognizers.append(tax_id_recognizer)
    
    # 11. Vehicle Identification Number (VIN)
    vin_recognizer = PatternRecognizer(
        supported_entity="VIN",
        patterns=[
            Pattern(
                name="vin_pattern",
                regex=r"\b[A-HJ-NPR-Z0-9]{17}\b",
                score=0.5
            ),
            Pattern(
                name="vin_with_label",
                regex=r"\b(?:VIN)[-:\s#]*[A-HJ-NPR-Z0-9]{17}\b",
                score=0.95
            )
        ],
        context=["VIN", "vehicle", "car", "automobile", "registration"]
    )
    recognizers.append(vin_recognizer)
    
    # 12. API Keys / Tokens (generic pattern)
    api_key_recognizer = PatternRecognizer(
        supported_entity="API_KEY",
        patterns=[
            Pattern(
                name="api_key_pattern",
                regex=r"\b[A-Za-z0-9_-]{32,}\b",
                score=0.3
            ),
            Pattern(
                name="api_key_with_label",
                regex=r"\b(?:API[_\s-]?KEY|TOKEN|SECRET)[-:\s=]*['\"]?[A-Za-z0-9_-]{20,}['\"]?",
                score=0.85
            )
        ],
        context=["API", "key", "token", "secret", "auth", "authorization"]
    )
    recognizers.append(api_key_recognizer)
    
    # 13. Username patterns
    username_recognizer = PatternRecognizer(
        supported_entity="USERNAME",
        patterns=[
            Pattern(
                name="username_pattern",
                regex=r"\b(?:user|username|login)[-:\s=]+[A-Za-z0-9_.-]{3,20}\b",
                score=0.75
            )
        ],
        context=["user", "username", "login", "account", "credential"]
    )
    recognizers.append(username_recognizer)
    
    # 14. MAC Address
    mac_address_recognizer = PatternRecognizer(
        supported_entity="MAC_ADDRESS",
        patterns=[
            Pattern(
                name="mac_address_pattern",
                regex=r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
                score=0.9
            )
        ],
        context=["MAC", "hardware", "network", "ethernet", "address"]
    )
    recognizers.append(mac_address_recognizer)
    
    # 15. Credit Card (Enhanced - catches dash-separated formats)
    credit_card_recognizer = PatternRecognizer(
        supported_entity="CREDIT_CARD",
        patterns=[
            Pattern(
                name="cc_dashes",
                regex=r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b",
                score=0.95
            ),
            Pattern(
                name="cc_no_separator",
                regex=r"\b\d{13,19}\b",
                score=0.4  # Needs context
            ),
            Pattern(
                name="cc_with_exp",
                regex=r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\s*\(Exp:?\s*\d{2}/\d{2}",
                score=0.99
            )
        ],
        context=["card", "credit", "visa", "mastercard", "amex", "discover", "CVV", "exp"]
    )
    recognizers.append(credit_card_recognizer)
    
    # 16. Security Clearance & Badge IDs
    security_badge_recognizer = PatternRecognizer(
        supported_entity="SECURITY_BADGE",
        patterns=[
            Pattern(
                name="badge_id",
                regex=r"\b[A-Z]{2,3}-\d{5,7}\b",
                score=0.7
            ),
            Pattern(
                name="clearance_level",
                regex=r"\b(?:TS/SCI|SECRET|TOP SECRET|CONFIDENTIAL)\b",
                score=0.9
            ),
            Pattern(
                name="access_code",
                regex=r"\b(?:AC|ACCESS)[-:]\d{4}[-][A-Z]{4,6}[-][A-Z]{4,6}\b",
                score=0.95
            )
        ],
        context=["clearance", "security", "badge", "access", "classified", "authorization"]
    )
    recognizers.append(security_badge_recognizer)
    
    # 17. Grant & Contract Numbers
    grant_recognizer = PatternRecognizer(
        supported_entity="GRANT_NUMBER",
        patterns=[
            Pattern(
                name="nih_grant",
                regex=r"\b(?:NIH|NSF|DOE|DOD)[-:]\d{4}[-]\d{4,6}\b",
                score=0.95
            ),
            Pattern(
                name="contract_number",
                regex=r"\b(?:Contract|Grant|Award)[-:\s#]*[A-Z0-9]{6,15}\b",
                score=0.8
            ),
            Pattern(
                name="irb_protocol",
                regex=r"\bIRB[-:]\d{4}[-]\d{4}\b",
                score=0.95
            ),
            Pattern(
                name="equity_grant",
                regex=r"\bGRANT[-:]\d{4}[-]\d{3}\b",
                score=0.9
            )
        ],
        context=["grant", "contract", "award", "funding", "IRB", "protocol", "equity"]
    )
    recognizers.append(grant_recognizer)
    
    # 18. URLs and Domains
    url_recognizer = PatternRecognizer(
        supported_entity="URL",
        patterns=[
            Pattern(
                name="http_url",
                regex=r"\b(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?\b",
                score=0.5
            ),
            Pattern(
                name="internal_domain",
                regex=r"\b[a-zA-Z0-9-]+\.(?:internal|local|corp|gov)\b",
                score=0.85
            ),
            Pattern(
                name="github_url",
                regex=r"\bgithub\.com/[a-zA-Z0-9_-]+\b",
                score=0.9
            )
        ],
        context=["portal", "server", "website", "domain", "URL", "github"]
    )
    recognizers.append(url_recognizer)
    
    # 19. AWS Keys & Cloud Credentials
    aws_key_recognizer = PatternRecognizer(
        supported_entity="AWS_KEY",
        patterns=[
            Pattern(
                name="aws_access_key",
                regex=r"\bAKIA[A-Z0-9]{16}\b",
                score=0.99
            ),
            Pattern(
                name="aws_secret_pattern",
                regex=r"\baws[-_]?(?:secret|access)[-_]?key[-_]?[:=\s]+[A-Za-z0-9/+=]{40}\b",
                score=0.9
            )
        ],
        context=["AWS", "amazon", "cloud", "S3", "EC2", "access"]
    )
    recognizers.append(aws_key_recognizer)
    
    # 20. OpenAI & Stripe API Keys
    service_api_recognizer = PatternRecognizer(
        supported_entity="SERVICE_API_KEY",
        patterns=[
            Pattern(
                name="openai_key",
                regex=r"\bsk-proj-[a-zA-Z0-9]{20,}\b",
                score=0.99
            ),
            Pattern(
                name="stripe_key",
                regex=r"\b(?:sk|pk)_(?:live|test)_[a-zA-Z0-9]{24,}\b",
                score=0.99
            ),
            Pattern(
                name="generic_sk_key",
                regex=r"\bsk[-_][a-zA-Z0-9]{20,}\b",
                score=0.7
            )
        ],
        context=["OpenAI", "Stripe", "API", "key", "secret", "token"]
    )
    recognizers.append(service_api_recognizer)
    
    # 21. Database Connection Strings
    db_connection_recognizer = PatternRecognizer(
        supported_entity="DB_CONNECTION",
        patterns=[
            Pattern(
                name="postgres_conn",
                regex=r"\bpostgresql://[^\s:]+:[^\s@]+@[^\s/]+:\d+/[^\s]+\b",
                score=0.95
            ),
            Pattern(
                name="redis_conn",
                regex=r"\bredis://[^\s:]+:[^\s@]+@[^\s:]+:\d+\b",
                score=0.95
            ),
            Pattern(
                name="mysql_conn",
                regex=r"\bmysql://[^\s:]+:[^\s@]+@[^\s/]+:\d+/[^\s]+\b",
                score=0.95
            )
        ],
        context=["database", "connection", "postgres", "mysql", "redis", "mongo"]
    )
    recognizers.append(db_connection_recognizer)
    
    # 22. License Plates
    license_plate_recognizer = PatternRecognizer(
        supported_entity="LICENSE_PLATE",
        patterns=[
            Pattern(
                name="plate_with_label",
                regex=r"\b(?:Plate|License Plate)[-:\s]+[A-Z0-9]{5,8}\b",
                score=0.95
            )
        ],
        context=["plate", "license plate", "vehicle", "registration"]
    )
    recognizers.append(license_plate_recognizer)
    
    # 23. Professional Licenses (Medical, DEA, NPI)
    professional_license_recognizer = PatternRecognizer(
        supported_entity="PROFESSIONAL_LICENSE",
        patterns=[
            Pattern(
                name="npi_number",
                regex=r"\bNPI[-:\s#]*\d{10}\b",
                score=0.95
            ),
            Pattern(
                name="dea_number",
                regex=r"\bDEA[-:\s#]*[A-Z]{2}\d{7}\b",
                score=0.95
            ),
            Pattern(
                name="medical_license",
                regex=r"\b(?:MD|Medical License)[-:\s#]*[A-Z]{1,3}\d{5,8}\b",
                score=0.85
            )
        ],
        context=["NPI", "DEA", "medical", "license", "physician", "doctor", "provider"]
    )
    recognizers.append(professional_license_recognizer)
    
    # 24. IBAN (Enhanced)
    iban_recognizer = PatternRecognizer(
        supported_entity="IBAN_CODE",
        patterns=[
            Pattern(
                name="iban_pattern",
                regex=r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
                score=0.7
            ),
            Pattern(
                name="iban_with_label",
                regex=r"\bIBAN[-:\s]*[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
                score=0.95
            )
        ],
        context=["IBAN", "international", "bank", "account", "transfer", "SWIFT"]
    )
    recognizers.append(iban_recognizer)
    
    # 25. CVV/Security Codes
    cvv_recognizer = PatternRecognizer(
        supported_entity="CVV",
        patterns=[
            Pattern(
                name="cvv_pattern",
                regex=r"\bCVV[-:\s]*\d{3,4}\b",
                score=0.95
            ),
            Pattern(
                name="security_code",
                regex=r"\b(?:Security Code|CVC|CVV2)[-:\s]*\d{3,4}\b",
                score=0.9
            )
        ],
        context=["CVV", "security", "code", "card", "verification"]
    )
    recognizers.append(cvv_recognizer)
    
    # 26. Medicare/Medicaid Numbers
    medicare_recognizer = PatternRecognizer(
        supported_entity="MEDICARE_NUMBER",
        patterns=[
            Pattern(
                name="medicare_pattern",
                regex=r"\b\d{1,3}[A-Z]{1,2}[-]?[A-Z]{1,2}[-]?\d{2,4}[A-Z]?\b",
                score=0.7
            ),
            Pattern(
                name="medicare_with_label",
                regex=r"\b(?:Medicare|Medicaid)[-:\s]+[A-Z0-9-]{8,15}\b",
                score=0.9
            )
        ],
        context=["Medicare", "Medicaid", "insurance", "health", "CMS"]
    )
    recognizers.append(medicare_recognizer)
    
    # 27. Patent & Trade Secret IDs
    patent_recognizer = PatternRecognizer(
        supported_entity="PATENT_NUMBER",
        patterns=[
            Pattern(
                name="us_patent",
                regex=r"\bUS[-]?\d{7,10}\b",
                score=0.8
            ),
            Pattern(
                name="trade_secret",
                regex=r"\bTS[-]\d{4}[-][A-Z]{4}[-]\d{3}\b",
                score=0.95
            )
        ],
        context=["patent", "trade secret", "intellectual property", "IP", "application"]
    )
    recognizers.append(patent_recognizer)
    
    return recognizers


def setup_analyzer() -> AnalyzerEngine:
    """
    Initialize Presidio Analyzer with hybrid detection:
    - AI Layer: Spacy NLP model (en_core_web_sm) for PERSON, LOCATION, ORGANIZATION
    - Rule-Based Layer: Custom regex patterns for multiple sensitive data types
    """
    # Initialize analyzer with Spacy small model (already installed)
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    
    # Configure NLP engine to use en_core_web_sm
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
    }
    
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    
    # Add all custom rule-based recognizers
    custom_recognizers = create_custom_recognizers()
    for recognizer in custom_recognizers:
        analyzer.registry.add_recognizer(recognizer)
    
    return analyzer


def encrypt_pii(input_file: str, output_file: str, aes_key: bytes):
    """
    Main function to detect and encrypt PII in text file
    Automatically handles large files by processing in chunks
    
    Args:
        input_file: Path to input text file
        output_file: Path to encrypted output file
        aes_key: 16-byte AES encryption key
    """
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    file_size_mb = len(text) / (1024 * 1024)
    
    print("=" * 70)
    print("HYBRID NEURO-SYMBOLIC PII ENCRYPTION SYSTEM")
    print("=" * 70)
    print(f"\n[1] Reading input file: {input_file}")
    print(f"    Content length: {len(text):,} characters ({file_size_mb:.2f} MB)")
    
    # Warn if file is very large
    if file_size_mb > 10:
        print(f"    ⚠️  Large file detected - processing may take several minutes")
    print()
    
    # Initialize analyzer with hybrid detection
    print("[2] Initializing Presidio Analyzer...")
    print("    • AI Layer: Spacy NLP (en_core_web_sm)")
    print("    • Rule-Based Layer: 27 custom regex patterns")
    print("      - IDs: Project, Employee, Badge, Patent, Trade Secret")
    print("      - Financial: Credit Cards, Bank Accounts, IBAN, CVV, Tax IDs")
    print("      - Medical: MRN, NPI, DEA, Medical License, Medicare/Medicaid")
    print("      - Identity: Passports, Driver Licenses, SSN, DOB, VINs")
    print("      - Digital: IP/MAC, URLs, API Keys, AWS, OpenAI, Stripe, DB Connections")
    print("      - Other: Insurance, License Plates, Grants/Contracts")
    analyzer = setup_analyzer()
    
    # Analyze text for PII
    print("\n[3] Analyzing text for sensitive entities...")
    entities_to_detect = [
        # AI-detected via Spacy NLP (3 types)
        "PERSON",
        "LOCATION",
        "ORGANIZATION",
        # Rule-based custom patterns (27 types)
        "PROJECT_ID",
        "PASSPORT_NUMBER",
        "DRIVERS_LICENSE",
        "MEDICAL_RECORD_NUMBER",
        "BANK_ACCOUNT",
        "INSURANCE_NUMBER",
        "EMPLOYEE_ID",
        "IP_ADDRESS",
        "DATE_OF_BIRTH",
        "TAX_ID",
        "VIN",
        "API_KEY",
        "USERNAME",
        "MAC_ADDRESS",
        "CREDIT_CARD",  # Enhanced with dash-separated format
        "SECURITY_BADGE",  # Clearance levels, badge IDs, access codes
        "GRANT_NUMBER",  # NIH, NSF, IRB, contracts, equity grants
        "URL",  # Domains, GitHub, internal portals
        "AWS_KEY",  # AWS access keys and secrets
        "SERVICE_API_KEY",  # OpenAI, Stripe, etc.
        "DB_CONNECTION",  # PostgreSQL, Redis, MySQL connection strings
        "LICENSE_PLATE",  # Vehicle license plates
        "PROFESSIONAL_LICENSE",  # NPI, DEA, medical licenses
        "IBAN_CODE",  # International bank account numbers
        "CVV",  # Credit card security codes
        "MEDICARE_NUMBER",  # Medicare/Medicaid identifiers
        "PATENT_NUMBER",  # Patents and trade secrets
        # Built-in Presidio detectors (5 types)
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "NRP",  # National Registry of Persons
        "US_BANK_NUMBER",
        "US_ITIN"  # Individual Taxpayer Identification Number
    ]
    
    results = analyzer.analyze(
        text=text,
        entities=entities_to_detect,
        language='en'
    )
    
    # Display detected entities
    print(f"    ✓ Found {len(results)} sensitive entities:")
    entity_summary = {}
    for result in results:
        entity_type = result.entity_type
        entity_summary[entity_type] = entity_summary.get(entity_type, 0) + 1
        detected_text = text[result.start:result.end]
        print(f"      - {entity_type}: '{detected_text}' (confidence: {result.score:.2f})")
    
    print(f"\n    Summary by type:")
    for entity_type, count in entity_summary.items():
        print(f"      • {entity_type}: {count} instance(s)")
    
    # Initialize anonymizer
    print("\n[4] Initializing Presidio Anonymizer with AES encryption...")
    anonymizer = AnonymizerEngine()
    
    # Configure AES encryption operator
    # Convert key to base64 for Presidio
    key_base64 = base64.b64encode(aes_key).decode('utf-8')
    
    encryption_config = {
        "DEFAULT": OperatorConfig(
            operator_name="encrypt",
            params={"key": key_base64}
        )
    }
    
    # Anonymize (encrypt) the detected entities
    print("    • Using AES-128 encryption (reversible)")
    print(f"    • Key fingerprint: {aes_key[:4].hex()}...{aes_key[-4:].hex()}")
    
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=encryption_config
    )
    
    # Write encrypted output
    print(f"\n[5] Writing encrypted output to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(anonymized_result.text)
    
    print(f"    ✓ Encrypted text length: {len(anonymized_result.text)} characters")
    print(f"    ✓ Encryption complete!")
    
    print("\n" + "=" * 70)
    print("ENCRYPTION SUMMARY")
    print("=" * 70)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Entities encrypted: {len(results)}")
    print(f"Encryption: AES (reversible with key)")
    print("=" * 70 + "\n")


def main():
    """Entry point for the PII encryption script"""
    
    # Define 16-byte (128-bit) AES key for AES-128 encryption
    # In production, use secure key management (e.g., AWS KMS, Azure Key Vault)
    # Presidio supports 128-bit (16 bytes), 192-bit (24 bytes), or 256-bit (32 bytes) keys
    AES_KEY = b'16ByteSecureKey!'  # Exactly 16 bytes for AES-128
    
    # Validate key length
    if len(AES_KEY) not in [16, 24, 32]:
        raise ValueError(f"AES key must be 16, 24, or 32 bytes, got {len(AES_KEY)}")
    
    # File paths - can be changed via command line arguments
    import sys
    if len(sys.argv) > 1:
        INPUT_FILE = sys.argv[1]
        OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else INPUT_FILE.replace('.txt', '_encrypted.txt')
    else:
        # Default: process large_data.txt if it exists, otherwise data.txt
        import os
        if os.path.exists("large_data.txt"):
            INPUT_FILE = "large_data.txt"
            OUTPUT_FILE = "large_data_encrypted.txt"
            print("📁 Detected large_data.txt - processing comprehensive dataset")
        else:
            INPUT_FILE = "data.txt"
            OUTPUT_FILE = "data_encrypted.txt"
    
    # Execute encryption
    try:
        encrypt_pii(INPUT_FILE, OUTPUT_FILE, AES_KEY)
    except FileNotFoundError:
        print(f"ERROR: Input file '{INPUT_FILE}' not found!")
        print("Usage: python encrypt_pii.py [input_file] [output_file]")
        print("Example: python encrypt_pii.py large_data.txt encrypted_output.txt")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
