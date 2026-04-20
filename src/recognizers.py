"""
recognizers.py — Custom Presidio PatternRecognizer definitions.

Single source of truth for all entity types not covered by Presidio's built-ins.
Import create_custom_recognizers() wherever an AnalyzerEngine needs them.
"""
from typing import List
from presidio_analyzer import PatternRecognizer, Pattern


def create_custom_recognizers() -> List[PatternRecognizer]:
    recognizers: List[PatternRecognizer] = []

    recognizers.append(PatternRecognizer(
        supported_entity="PROJECT_ID",
        patterns=[Pattern("project_id_pattern", r"\bPROJ-\d{4}\b", 0.9)],
        context=["project", "trial", "research", "enrolled"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="PASSPORT_NUMBER",
        patterns=[
            Pattern("us_passport_9digit", r"\b\d{9}\b", 0.5),
            Pattern("us_passport_letter", r"\b[A-Z]\d{8}\b", 0.6),
        ],
        context=["passport", "travel", "document", "citizenship", "visa"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="DRIVERS_LICENSE",
        patterns=[
            Pattern("dl_letter_numbers", r"\b[A-Z]{1,2}\d{6,8}\b", 0.6),
            Pattern("dl_numbers_only", r"\b\d{7,9}\b", 0.4),
        ],
        context=["license", "driver", "DMV", "state ID", "identification"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MEDICAL_RECORD_NUMBER",
        patterns=[
            Pattern("mrn_pattern", r"\bMRN[-:]?\s*\d{6,10}\b", 0.95),
            Pattern("patient_id", r"\b(?:Patient|PT)[-:]?\s*\d{6,10}\b", 0.85),
        ],
        context=["patient", "medical", "hospital", "clinic", "chart"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="BANK_ACCOUNT",
        patterns=[
            Pattern("bank_account_pattern", r"\b\d{8,17}\b", 0.3),
            Pattern("account_with_prefix", r"\b(?:Account|Acct)[-:\s#]*\d{8,17}\b", 0.85),
        ],
        context=["account", "bank", "routing", "checking", "savings", "deposit"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="INSURANCE_NUMBER",
        patterns=[
            Pattern("insurance_policy", r"\b[A-Z]{2,4}\d{6,12}\b", 0.6),
            Pattern("policy_with_prefix", r"\b(?:Policy|Member|Group)[-:\s#]*[A-Z0-9]{6,15}\b", 0.8),
        ],
        context=["insurance", "policy", "coverage", "claim", "beneficiary", "premium"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="EMPLOYEE_ID",
        patterns=[Pattern("emp_id_pattern", r"\b(?:EMP|E|EMPL)[-:]?\d{4,8}\b", 0.85)],
        context=["employee", "staff", "personnel", "worker", "payroll"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern("dob_mmddyyyy", r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b", 0.6),
            Pattern("dob_with_label", r"\b(?:DOB|Birth|Born)[-:\s]+(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2,4}\b", 0.85),
        ],
        context=["birth", "DOB", "born", "age", "birthday"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="TAX_ID",
        patterns=[
            Pattern("ein_pattern", r"\b\d{2}-\d{7}\b", 0.7),
            Pattern("ein_with_label", r"\b(?:EIN|Tax ID)[-:\s#]*\d{2}-?\d{7}\b", 0.9),
        ],
        context=["EIN", "tax", "employer", "federal", "IRS"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="VIN",
        patterns=[
            Pattern("vin_pattern", r"\b[A-HJ-NPR-Z0-9]{17}\b", 0.5),
            Pattern("vin_with_label", r"\b(?:VIN)[-:\s#]*[A-HJ-NPR-Z0-9]{17}\b", 0.95),
        ],
        context=["VIN", "vehicle", "car", "automobile", "registration"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="API_KEY",
        patterns=[
            Pattern("api_key_pattern", r"\b[A-Za-z0-9_-]{32,}\b", 0.3),
            Pattern("api_key_with_label", r"\b(?:API[_\s-]?KEY|TOKEN|SECRET)[-:\s=]*['\"]?[A-Za-z0-9_-]{20,}['\"]?", 0.85),
        ],
        context=["API", "key", "token", "secret", "auth", "authorization"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="USERNAME",
        patterns=[
            Pattern("username_pattern", r"\b(?:user|username|login)[-:\s=]+[A-Za-z0-9_.-]{3,20}\b", 0.75),
            Pattern("username_bare", r"\b[a-z][a-z0-9]{2,15}_(?:admin|dev|user|secure|ops|root|sys)\b", 0.7),
        ],
        context=["user", "username", "login", "account", "credential"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MAC_ADDRESS",
        patterns=[Pattern("mac_address_pattern", r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", 0.9)],
        context=["MAC", "hardware", "network", "ethernet", "address"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="SECURITY_BADGE",
        patterns=[
            Pattern("badge_id", r"\b[A-Z]{2,3}-\d{5,7}\b", 0.75),
            # Use (?<!\w)/(?!\w) instead of \b so TS/SCI matches despite the slash
            Pattern("clearance_level", r"(?<!\w)(?:TS/SCI|TOP\s+SECRET|SECRET|CONFIDENTIAL)(?!\w)", 0.9),
            Pattern("access_code", r"\b(?:AC|ACCESS)[-:]\d{4}[-][A-Z]{4,6}[-][A-Z]{4,6}\b", 0.95),
        ],
        context=["clearance", "security", "badge", "access", "classified", "authorization",
                 "badge", "ID", "personnel"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="GRANT_NUMBER",
        patterns=[
            Pattern("nih_grant", r"\b(?:NIH|NSF|DOE|DOD)[-:]\d{4}[-]\d{4,6}\b", 0.95),
            Pattern("contract_number", r"\b(?:Contract|Grant|Award)[-:\s#]*[A-Z0-9]{6,15}\b", 0.8),
            Pattern("irb_protocol", r"\bIRB[-:]\d{4}[-]\d{4}\b", 0.95),
            Pattern("equity_grant", r"\bGRANT[-:]\d{4}[-]\d{3}\b", 0.9),
        ],
        context=["grant", "contract", "award", "funding", "IRB", "protocol", "equity"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="AWS_KEY",
        patterns=[
            Pattern("aws_access_key", r"\bAKIA[A-Z0-9]{16}\b", 0.99),
            Pattern("aws_secret_pattern", r"\baws[-_]?(?:secret|access)[-_]?key[-_]?[:=\s]+[A-Za-z0-9/+=]{40}\b", 0.9),
        ],
        context=["AWS", "amazon", "cloud", "S3", "EC2", "access"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="SERVICE_API_KEY",
        patterns=[
            Pattern("openai_key", r"\bsk-proj-[a-zA-Z0-9]{20,}\b", 0.99),
            Pattern("stripe_key", r"\b(?:sk|pk)_(?:live|test)_[a-zA-Z0-9]{24,}\b", 0.99),
            Pattern("generic_sk_key", r"\bsk[-_][a-zA-Z0-9]{20,}\b", 0.7),
        ],
        context=["OpenAI", "Stripe", "API", "key", "secret", "token"]
    ))

    # Auth and trailing /dbname are optional so bare URIs are still caught
    recognizers.append(PatternRecognizer(
        supported_entity="DB_CONNECTION",
        patterns=[
            Pattern("postgres_conn",
                    r"\bpostgresql://(?:[^\s@]+@)?[^\s/]+(?::\d+)?(?:/[^\s]*)?\b", 0.95),
            Pattern("redis_conn",
                    r"\bredis://(?:[^\s@]+@)?[^\s:]+:\d+\b", 0.95),
            Pattern("mysql_conn",
                    r"\bmysql://(?:[^\s@]+@)?[^\s/]+(?::\d+)?(?:/[^\s]*)?\b", 0.95),
        ],
        context=["database", "connection", "postgres", "mysql", "redis", "mongo"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="LICENSE_PLATE",
        patterns=[Pattern("plate_with_label", r"\b(?:Plate|License Plate)[-:\s]+[A-Z0-9]{5,8}\b", 0.95)],
        context=["plate", "license plate", "vehicle", "registration"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="PROFESSIONAL_LICENSE",
        patterns=[
            Pattern("npi_number", r"\bNPI[-:\s#]*\d{10}\b", 0.95),
            Pattern("npi_bare", r"\b\d{10}\b", 0.4),
            Pattern("dea_number", r"\bDEA[-:\s#]*[A-Z]{2}\d{7}\b", 0.95),
            Pattern("dea_bare", r"\b[A-Z]{2}\d{7}\b", 0.5),
            Pattern("medical_license", r"\b(?:MD|Medical License)[-:\s#]*[A-Z]{1,3}\d{5,8}\b", 0.85),
        ],
        context=["NPI", "DEA", "medical", "license", "physician", "doctor", "provider"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="CVV",
        patterns=[
            Pattern("cvv_pattern", r"\bCVV[-:\s]*\d{3,4}\b", 0.95),
            Pattern("security_code", r"\b(?:Security Code|CVC|CVV2)[-:\s]*\d{3,4}\b", 0.9),
        ],
        context=["CVV", "security", "code", "card", "verification"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MEDICARE_NUMBER",
        patterns=[
            Pattern("medicare_pattern", r"\b\d{1,3}[A-Z]{1,2}[-]?[A-Z]{1,2}[-]?\d{2,4}[A-Z]?\b", 0.7),
            Pattern("medicare_with_label", r"\b(?:Medicare|Medicaid)[-:\s]+[A-Z0-9-]{8,15}\b", 0.9),
        ],
        context=["Medicare", "Medicaid", "insurance", "health", "CMS"]
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="PATENT_NUMBER",
        patterns=[
            Pattern("us_patent", r"\bUS[-]?\d{4}[-]\d{6}\b", 0.85),
            Pattern("trade_secret", r"\bTS[-]\d{4}[-][A-Z]{2,8}[-]\d{3}\b", 0.9),
            Pattern("patent_app", r"\b[A-Z]{2}[-]?\d{7,10}[A-Z]?\d?\b", 0.5),
        ],
        context=["patent", "trade secret", "intellectual property", "IP", "application",
                 "filing", "registration"]
    ))

    return recognizers
