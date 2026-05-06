"""
generate_synthetic_docs.py — Generate diverse synthetic documents for LLM training.

Produces five record types matching the tux.ai large_data.txt templates:
  1. Personal Banking Customer
  2. International Business Client
  3. Government Contractor
  4. Healthcare Professional
  5. Tech Startup Employee

All values are fake (Faker-generated). Output goes to raw_temp/ and will be
securely deleted by prepare_corpus.py after tokenization.
"""

import argparse
import os
import random
import sys
from typing import Callable

from faker import Faker

RECORD_TYPES = [
    "personal_banking",
    "intl_business",
    "gov_contractor",
    "healthcare_professional",
    "tech_startup",
]

_VIN_CHARS = list("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")


def _vin(fake: Faker) -> str:
    return "".join(fake.random_choices(elements=_VIN_CHARS, length=17))


def _api_key(fake: Faker) -> str:
    return "sk_live_" + fake.lexify("?" * 32, letters="abcdefghijklmnopqrstuvwxyz0123456789")


def _mac(fake: Faker) -> str:
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _mrn(fake: Faker) -> str:
    return f"MRN-{fake.random_int(min=100000, max=999999)}"


def _emp_id(fake: Faker) -> str:
    return f"EMP-{fake.random_int(min=1000, max=9999)}"


def _policy(fake: Faker) -> str:
    return f"POL{fake.random_int(min=100000, max=999999)}"


def _badge(fake: Faker) -> str:
    return f"BADGE-{fake.lexify('????').upper()}-{fake.random_int(min=1000, max=9999)}"


def _project(fake: Faker) -> str:
    return f"PROJ-{fake.lexify('????').upper()}-{fake.random_int(min=100, max=999)}"


def _grant(fake: Faker) -> str:
    return f"NIH-{fake.random_int(min=2020, max=2025)}-{fake.random_int(min=10000, max=99999)}"


def _routing(fake: Faker) -> str:
    return str(fake.random_int(min=100000000, max=999999999))


def _account(fake: Faker) -> str:
    return str(fake.random_int(min=10000000000, max=99999999999))


def _itin(fake: Faker) -> str:
    return f"9{fake.random_int(min=10, max=99)}-{fake.random_int(min=10, max=99)}-{fake.random_int(min=1000, max=9999)}"


def _dea(fake: Faker) -> str:
    return f"A{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"


def _npi(fake: Faker) -> str:
    return str(fake.random_int(min=1000000000, max=9999999999))


def make_personal_banking(fake: Faker, rng: random.Random) -> str:
    title = rng.choice(["", "Mr. ", "Ms. ", "Mrs. "])
    name = f"{title}{fake.name()}"
    dob = fake.date_of_birth(minimum_age=22, maximum_age=75).strftime("%m/%d/%Y")
    ssn = fake.ssn()
    email = fake.email()
    phone = fake.phone_number()
    city = fake.city()
    state = fake.state_abbr()
    zip_code = fake.zipcode()
    street = fake.street_address()

    bank_acct = _account(fake)
    routing = _routing(fake)
    cc = fake.credit_card_number(card_type=rng.choice(["visa", "mastercard"]))
    cc_exp = fake.credit_card_expire()
    cvv = str(fake.random_int(min=100, max=999))
    tax_id = f"TIN-{fake.random_int(min=10, max=99)}-{fake.random_int(min=1000000, max=9999999)}"
    income = rng.choice([85000, 110000, 125000, 150000, 200000])

    employer = fake.company()
    emp_id = _emp_id(fake)
    work_email = fake.company_email()
    project = _project(fake)

    mrn = _mrn(fake)
    ins_policy = _policy(fake)
    doctor = f"Dr. {fake.last_name()}"
    hospital = rng.choice([
        "Massachusetts General Hospital", "Johns Hopkins Hospital",
        "Cleveland Clinic", "Mayo Clinic", "UCSF Medical Center",
    ])
    last_visit = fake.date_this_decade().strftime("%m/%d/%Y")

    username = fake.user_name()
    api_key = _api_key(fake)
    oauth = _api_key(fake)
    ip = fake.ipv4_private()
    mac = _mac(fake)

    vin = _vin(fake)
    plate = f"{fake.state_abbr()}-{fake.lexify('???').upper()}-{fake.random_int(min=100, max=9999)}"
    dl = f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"
    dl_state = fake.state_abbr()

    sep = rng.choice(["", " "])

    return f"""CUSTOMER DATABASE - DO NOT DISTRIBUTE
========================================================

CUSTOMER RECORDS - FINANCIAL SERVICES DIVISION

Record: Personal Banking Customer
-------------------------------------
Name: {name}
DOB: {dob}
SSN: {ssn}
Email:{sep}{email}
Phone: {phone}
Address: {street}, {city}, {state} {zip_code}

Financial Information:
- Bank Account: {bank_acct}
- Routing Number: {routing}
- Credit Card: {cc} (Exp: {cc_exp}, CVV: {cvv})
- Tax ID: {tax_id}
- Annual Income: ${income:,}

Employment:
- Employer: {employer}
- Employee ID: {emp_id}
- Work Email: {work_email}
- Project Assignment: {project}

Medical Information (HIPAA Protected):
- Medical Record Number (MRN): {mrn}
- Health Insurance: Policy: {ins_policy}
- Primary Care: {doctor} at {hospital}
- Last Visit: {last_visit}

Digital Credentials:
- Username: {username}
- API Key: {api_key}
- OAuth Token: {oauth}
- Network IP: {ip}
- MAC Address: {mac}

Vehicle Information:
- VIN: {vin}
- License Plate: {plate}
- Driver License: {dl} ({dl_state})

========================================================
"""


def make_intl_business(fake: Faker, rng: random.Random) -> str:
    prefix = rng.choice(["Dr. ", "Prof. ", ""])
    name = f"{prefix}{fake.name()}"
    dob = fake.date_of_birth(minimum_age=30, maximum_age=65).strftime("%B %d, %Y")
    passport = str(fake.random_int(min=100000000, max=999999999))
    ssn = fake.ssn()
    email = fake.email()
    phone1 = fake.phone_number()
    phone2 = fake.phone_number()

    company = fake.company() + rng.choice([" Ltd", " Inc", " GmbH", " S.A."])
    tax_id = f"EIN-{fake.random_int(min=10, max=99)}-{fake.random_int(min=1000000, max=9999999)}"
    iban = fake.iban()
    biz_acct = _account(fake)
    corp_card = fake.credit_card_number(card_type="mastercard")

    emp_id = _emp_id(fake)
    vpn_ip = fake.ipv4_private()
    server_ip = fake.ipv4_private()
    mac = _mac(fake)
    api_secret = _api_key(fake)

    proj1 = _project(fake)
    proj2 = _project(fake)
    grant = _grant(fake)
    proj3 = _project(fake)

    mrn1 = _mrn(fake)
    mrn2 = _mrn(fake)
    ins = _policy(fake)
    diag_ip = fake.ipv4_private()

    return f"""INTERNATIONAL BUSINESS CLIENT PROFILE
========================================================

Record: International Business Client
-------------------------------------
Name: {name}
DOB: Born {dob}
Passport: {passport}
SSN: {ssn}
Email: {email}
Phone: +1 {phone1}
Mobile: {phone2}

Business Information:
- Company: {company}
- Tax ID: {tax_id}
- IBAN: {iban}
- Business Account: {biz_acct}
- Corporate Card: {corp_card}

IT Infrastructure:
- Employee ID: {emp_id}
- VPN IP: {vpn_ip}
- Server IP: {server_ip}
- MAC Address: {mac}
- API Secret: {api_secret}

Research Projects:
- Active in {proj1}
- Clinical trial enrollment: {proj2}
- Grant {grant} ID: {proj3}

Medical Data (Protected Health Information):
- Patient ID: {mrn1}
- MRN: {mrn2}
- Insurance: Policy {ins}
- Diagnosis codes stored on {diag_ip}

========================================================
"""


def make_gov_contractor(fake: Faker, rng: random.Random) -> str:
    rank = rng.choice(["Colonel", "Major", "Captain", "Sergeant", "Lieutenant"])
    name = f"{rank} {fake.last_name()} (Ret.)"
    dob = fake.date_of_birth(minimum_age=35, maximum_age=70).strftime("%m/%d/%Y")
    ssn = fake.ssn()
    itin = _itin(fake)
    passport = str(fake.random_int(min=100000000, max=999999999))
    email = fake.email()
    phone = fake.phone_number()

    clearance = rng.choice(["TOP SECRET/SCI", "SECRET", "TOP SECRET", "SECRET/SCI"])
    badge1 = _badge(fake)
    badge2 = _badge(fake)
    emp_id = _emp_id(fake)
    access_code = fake.lexify("????").upper() + str(fake.random_int(min=1000, max=9999))

    bank_acct = _account(fake)
    contract = f"GS-{fake.random_int(min=10, max=99)}F-{fake.random_int(min=10000, max=99999)}"
    billing_acct = _account(fake)
    cc = fake.credit_card_number()

    mac = _mac(fake)
    vpn_ip = fake.ipv4_private()
    portal_url = f"https://secureportal.{fake.domain_name()}"
    username = fake.user_name()
    token = _api_key(fake)

    vin1 = _vin(fake)
    vin2 = _vin(fake)
    dl = f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"
    dl_state = fake.state_abbr()

    proj1 = _project(fake)
    proj2 = _project(fake)
    proj3 = _project(fake)

    va_id = _badge(fake)
    mrn = _mrn(fake)
    medicare = f"1{fake.random_int(min=10000000, max=99999999)}A"
    facility = rng.choice([
        "Walter Reed National Military Medical Center",
        "Bethesda Naval Hospital",
        "Fort Belvoir Community Hospital",
    ])

    return f"""GOVERNMENT CONTRACTOR PERSONNEL FILE
========================================================

Record: Government Contractor
-------------------------------------
Name: {name}
DOB: {dob}
SSN: {ssn}
ITIN: {itin}
Passport: {passport}
Email: {email}
Phone: {phone}

Clearance Information:
- Security Clearance: {clearance}
- Badge ID: {badge1}
- Employee ID: {emp_id}
- Access Code: {access_code}

Financial:
- Bank Account: {bank_acct}
- Government Contract: {contract}
- Billing Account: {billing_acct}
- Credit Card: {cc}

Technology Assets:
- Work Laptop MAC: {mac}
- VPN IP Address: {vpn_ip}
- Secure Portal: {portal_url} (User: {username})
- Access Token: {token}

Vehicles (Government Fleet):
- Primary: VIN {vin1}
- Secondary: VIN {vin2}
- Driver License: {dl} ({dl_state})

Projects:
- Defense Contract {proj1}
- Research Initiative {proj2}
- Training Program {proj3}

Medical (VA Records):
- VA ID: {va_id}
- MRN: {mrn}
- Insurance: {medicare}
- Treatment at: {facility}

========================================================
"""


def make_healthcare_professional(fake: Faker, rng: random.Random) -> str:
    suffix = rng.choice(["MD", "DO", "PhD", "MD, PhD"])
    name = f"Dr. {fake.name()}, {suffix}"
    city = fake.city()
    state = fake.state_abbr()
    dob = fake.date_of_birth(minimum_age=30, maximum_age=65).strftime("%m/%d/%Y")
    ssn = fake.ssn()
    prof_license = f"MD-{state}-{fake.random_int(min=100000, max=999999)}"
    med_license_state = fake.state_abbr()
    dea = _dea(fake)
    npi = _npi(fake)
    email = fake.email()
    phone = fake.phone_number()

    hospital = rng.choice([
        "Harvard Medical School", "Johns Hopkins Hospital",
        "Mayo Clinic", "Cleveland Clinic", "Stanford Medical Center",
        "UCSF Medical Center", "UCLA Medical Center",
    ])
    emp_id = _emp_id(fake)
    dept = rng.choice(["Cardiology", "Oncology", "Neurology", "Orthopedics", "Radiology"])
    campus = fake.city()
    office_ip = fake.ipv4_private()

    patient1_name = fake.name()
    mrn1 = _mrn(fake)
    dob1 = fake.date_of_birth().strftime("%m/%d/%Y")
    ssn1 = fake.ssn()
    mrn2 = _mrn(fake)
    dob2 = fake.date_of_birth().strftime("%m/%d/%Y")
    mrn3 = _mrn(fake)
    ins3 = _policy(fake)

    proj = _project(fake)
    grant1 = _grant(fake)
    grant2 = _grant(fake)
    data_ip = fake.ipv4_private()

    bank_acct = _account(fake)
    ins_policy = _policy(fake)
    tax_id = f"TIN-{fake.random_int(min=10, max=99)}-{fake.random_int(min=1000000, max=9999999)}"
    cc = fake.credit_card_number()

    username = fake.user_name()
    api_key = _api_key(fake)
    mac = _mac(fake)

    vin = _vin(fake)
    dl = f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"
    dl_state = med_license_state

    return f"""HEALTHCARE PROFESSIONAL PROFILE
========================================================

Record: Healthcare Professional
-------------------------------------
{name}
Location: {city}, {state}
Born: {dob}
SSN: {ssn}
Professional License: {prof_license}
Medical License: {med_license_state} ({med_license_state})
DEA: {dea}
NPI: {npi}
Email: {email}
Phone: {phone}

Employment:
- Hospital: {hospital}
- Employee ID: {emp_id}
- Department: {dept}, {campus} campus
- Office IP: {office_ip}

Patients (Sample - De-identification Required):
1. {patient1_name} - {mrn1}, DOB: {dob1}, SSN: {ssn1}
2. Patient ID: {mrn2}, Born {dob2}
3. Robert Johnson - {mrn3}, Insurance Policy: {ins3}

Research:
- Clinical Trial: {proj}
- Grant: {grant1}
- IRB Protocol: IRB-2023-{fake.random_int(min=10000, max=99999)}
- Data Server: {data_ip}

Financial:
- Bank Account: {bank_acct}
- Professional Liability Insurance: Policy {ins_policy}
- Tax ID: {tax_id}
- Credit Card: {cc}

Technology:
- Work Login: {username}
- Hospital Portal API: {api_key}
- MAC Address: {mac}

Vehicle:
- Personal: VIN {vin}
- Driver License: {dl} ({dl_state})

========================================================
"""


def make_tech_startup(fake: Faker, rng: random.Random) -> str:
    name = fake.name()
    username = fake.user_name()
    dob = fake.date_of_birth(minimum_age=22, maximum_age=45).strftime("%m/%d/%Y")
    ssn = fake.ssn()
    email = fake.email()
    personal_email = fake.free_email()
    phone = fake.phone_number()

    company = fake.company() + rng.choice([" Inc", " Labs", " AI", " Technologies"])
    city = fake.city()
    emp_id = _emp_id(fake)
    tax_id = f"EIN-{fake.random_int(min=10, max=99)}-{fake.random_int(min=1000000, max=9999999)}"
    grant = f"GRANT-{fake.random_int(min=2020, max=2025)}-{fake.random_int(min=10000, max=99999)}"
    project = _project(fake)

    bank_acct = _account(fake)
    venmo = f"@{fake.user_name()}"
    paypal = fake.email()
    cc = fake.credit_card_number(card_type="visa")

    github = fake.user_name()
    aws_key = f"AKIA{fake.lexify('?' * 16, letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}"
    aws_secret = fake.lexify("?" * 40, letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/")
    db_host = f"db.{fake.domain_name()}"
    db_user = fake.user_name()
    db_pass = fake.password(length=16)
    db_name = fake.slug().replace("-", "_")
    work_ip = fake.ipv4_private()
    mac = _mac(fake)
    api_key = _api_key(fake)

    vin = _vin(fake)
    dl = f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"
    dl_state = fake.state_abbr()

    ssn2 = fake.ssn()
    med_ins = _policy(fake)
    mrn = _mrn(fake)
    dob2 = fake.date_of_birth().strftime("%m/%d/%Y")

    return f"""TECH STARTUP EMPLOYEE PROFILE
========================================================

Record: Tech Startup Employee
-------------------------------------
Name: {name}
Username: {username}
DOB: {dob}
SSN: {ssn}
Email: {email}
Personal Email: {personal_email}
Phone: {phone}

Employment:
- Company: {company} ({city})
- Employee ID: {emp_id}
- Tax ID: {tax_id}
- Equity Grant ID: {grant}
- Project: {project}

Financial:
- Bank Account: {bank_acct}
- Venmo: {venmo}
- PayPal: {paypal}
- Credit Card: {cc}

Development Credentials:
- GitHub: {github}
- AWS Access Key: {aws_key}
- AWS Secret Key: {aws_secret}
- DB Connection: postgresql://{db_user}:{db_pass}@{db_host}/{db_name}
- Work IP: {work_ip}
- MAC Address: {mac}
- API Token: {api_key}

Vehicle:
- VIN: {vin}
- Driver License: {dl} ({dl_state})

Medical (Employer Plan):
- Dependent SSN: {ssn2}
- Insurance: {med_ins}
- MRN: {mrn}
- DOB on file: {dob2}

========================================================
"""


_GENERATORS: dict[str, Callable[[Faker, random.Random], str]] = {
    "personal_banking":        make_personal_banking,
    "intl_business":           make_intl_business,
    "gov_contractor":          make_gov_contractor,
    "healthcare_professional": make_healthcare_professional,
    "tech_startup":            make_tech_startup,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic PII documents for LLM training corpus."
    )
    parser.add_argument("--count", type=int, default=1000,
                        help="Total number of documents to generate (default: 1000)")
    parser.add_argument("--output-dir", default="llm/data/raw_temp",
                        help="Output directory for raw documents (default: llm/data/raw_temp)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    fake = Faker()
    Faker.seed(args.seed)
    rng = random.Random(args.seed)

    per_type = args.count // len(RECORD_TYPES)
    remainder = args.count % len(RECORD_TYPES)

    counts = {t: per_type for t in RECORD_TYPES}
    for t in RECORD_TYPES[:remainder]:
        counts[t] += 1

    manifest: dict[str, int] = {}
    total = 0

    for record_type in RECORD_TYPES:
        n = counts[record_type]
        gen = _GENERATORS[record_type]
        for i in range(n):
            doc = gen(fake, rng)
            filename = f"{record_type}_{i:06d}.txt"
            path = os.path.join(args.output_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(doc)
            total += 1
        manifest[record_type] = n

    print(f"\nGenerated {total} documents in {args.output_dir}/")
    print("Manifest:")
    for rtype, count in manifest.items():
        print(f"  {rtype:<30} {count:>4} documents")


if __name__ == "__main__":
    main()
