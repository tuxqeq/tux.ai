import argparse
import json
import random
import re
from faker import Faker
from tqdm import tqdm
import os

fake = Faker()

KEY_TO_LABEL = {
    "name": "PER", "address": "LOC", "company": "ORG",
    "email": "EMAIL", "phone_number": "PHONE", "ssn": "SSN",
    "credit_card_number": "CREDIT_CARD", "dob": "DOB",
    "license": "LICENSE", "passport": "PASSPORT",
    "ip_address": "IP_ADDRESS", "mrn": "MRN",
    "bank_account": "BANK_ACCOUNT", "username": "USERNAME",
    "vin": "VIN", "api_key": "API_KEY",
    "mac_address": "MAC", "emp_id": "EMP_ID",
    "insurance": "INSURANCE",
}

_VIN_CHARS = list("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")


def make_value(key: str) -> str:
    generators = {
        "name":               lambda: fake.name(),
        "email":              lambda: fake.email(),
        "address":            lambda: fake.address().replace("\n", ", "),
        "phone_number":       lambda: fake.phone_number(),
        "credit_card_number": lambda: fake.credit_card_number(),
        "ssn":                lambda: fake.ssn(),
        "company":            lambda: fake.company(),
        "dob":                lambda: fake.date_of_birth().strftime("%m/%d/%Y"),
        "license":            lambda: f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}",
        "passport":           lambda: str(fake.random_int(min=100000000, max=999999999)),
        "ip_address":         lambda: fake.ipv4(),
        "mrn":                lambda: f"MRN-{fake.random_int(min=100000, max=999999)}",
        "bank_account":       lambda: str(fake.random_int(min=10000000000, max=99999999999)),
        "username":           lambda: fake.user_name(),
        "vin":                lambda: "".join(fake.random_choices(elements=_VIN_CHARS, length=17)),
        "api_key":            lambda: "sk_live_" + fake.lexify("?" * 32, letters="abcdefghijklmnopqrstuvwxyz0123456789"),
        "mac_address":        lambda: ":".join(f"{fake.random_int(0, 255):02X}" for _ in range(6)),
        "emp_id":             lambda: f"EMP-{fake.random_int(min=1000, max=9999)}",
        "insurance":          lambda: f"POL{fake.random_int(min=100000, max=999999)}",
    }
    return generators[key]() if key in generators else key


def generate_data(count, output_file):
    data = []

    templates = [
        # ===== NAMES (Person) =====
        ("My name is {name}.", ["name"]),
        ("Please update the record for {name}.", ["name"]),
        ("Contact {name} at {phone_number}.", ["name", "phone_number"]),
        ("The meeting is with {name} from {company}.", ["name", "company"]),
        ("Ask {name} about the project.", ["name"]),
        ("I'm meeting {name} tomorrow.", ["name"]),
        ("Give this to {name}.", ["name"]),
        ("Is {name} available?", ["name"]),
        ("Please tell {name} I called.", ["name"]),
        ("{name} works in the finance department.", ["name"]),
        ("The report was prepared by {name}.", ["name"]),
        ("Dr. {name} will see you now.", ["name"]),
        ("Patient {name} arrived at 3pm.", ["name"]),
        ("{name} submitted the application.", ["name"]),
        ("Schedule a call with {name}.", ["name"]),
        
        # ===== EMAILS =====
        ("You can reach me at {email}.", ["email"]),
        ("The invoice was sent to {email}.", ["email"]),
        ("Is {email} your correct email?", ["email"]),
        ("Send the document to {email}.", ["email"]),
        ("Contact support at {email}.", ["email"]),
        ("My email is {email}.", ["email"]),
        ("Reply to {email} with the details.", ["email"]),
        ("Forward this to {email}.", ["email"]),
        ("Email address on file: {email}", ["email"]),
        ("Notification sent to {email}.", ["email"]),
        ("Please verify {email} to continue.", ["email"]),
        ("Primary contact email: {email}", ["email"]),
        ("CC {email} on this thread.", ["email"]),
        ("Registration confirmed for {email}.", ["email"]),

        # ===== PHONE NUMBERS =====
        ("Call me at {phone_number}.", ["phone_number"]),
        ("My phone number is {phone_number}.", ["phone_number"]),
        ("You can reach me at {phone_number}.", ["phone_number"]),
        ("Contact number: {phone_number}", ["phone_number"]),
        ("Call {phone_number} for support.", ["phone_number"]),
        ("Mobile: {phone_number}", ["phone_number"]),
        ("Office phone: {phone_number}", ["phone_number"]),
        ("Emergency contact: {phone_number}", ["phone_number"]),
        ("Text us at {phone_number}.", ["phone_number"]),
        ("Fax number: {phone_number}", ["phone_number"]),
        ("Direct line: {phone_number}", ["phone_number"]),
        ("Callback number is {phone_number}.", ["phone_number"]),

        # ===== SSN =====
        ("His SSN is {ssn}.", ["ssn"]),
        ("Social Security Number: {ssn}", ["ssn"]),
        ("Patient SSN {ssn} was verified.", ["ssn"]),
        ("SSN on file: {ssn}", ["ssn"]),
        ("Tax ID {ssn} confirmed.", ["ssn"]),
        ("Please provide SSN {ssn} for enrollment.", ["ssn"]),
        ("SSN verification required: {ssn}", ["ssn"]),
        ("Social security {ssn} matched.", ["ssn"]),
        ("Identity confirmed via SSN {ssn}.", ["ssn"]),
        ("SSN {ssn} linked to account.", ["ssn"]),

        # ===== CREDIT CARDS =====
        ("My credit card number is {credit_card_number}.", ["credit_card_number"]),
        ("Card ending in {credit_card_number}.", ["credit_card_number"]),
        ("Payment via card {credit_card_number}.", ["credit_card_number"]),
        ("Credit card {credit_card_number} authorized.", ["credit_card_number"]),
        ("Charge to card {credit_card_number}.", ["credit_card_number"]),
        ("Transaction declined for {credit_card_number}.", ["credit_card_number"]),
        ("Please verify card number {credit_card_number}.", ["credit_card_number"]),
        ("Refund issued to {credit_card_number}.", ["credit_card_number"]),
        ("Card on file: {credit_card_number}", ["credit_card_number"]),
        ("Billing card {credit_card_number} updated.", ["credit_card_number"]),

        # ===== ADDRESSES =====
        ("I live at {address}.", ["address"]),
        ("Send the package to {address}.", ["address"]),
        ("Delivery address: {address}", ["address"]),
        ("Mailing address is {address}.", ["address"]),
        ("Shipping to {address}.", ["address"]),
        ("Office located at {address}.", ["address"]),
        ("Billing address: {address}", ["address"]),
        ("Return to sender at {address}.", ["address"]),
        ("Current residence: {address}", ["address"]),
        ("Physical address on record: {address}", ["address"]),
        ("Please update your address to {address}.", ["address"]),
        ("Home address confirmed as {address}.", ["address"]),

        # ===== COMPANIES/ORGANIZATIONS =====
        ("I work at {company}.", ["company"]),
        ("{company} announced new policies today.", ["company"]),
        ("The contract with {company} was signed.", ["company"]),
        ("Partnership with {company} established.", ["company"]),
        ("{company} is our main client.", ["company"]),
        ("Invoice issued to {company}.", ["company"]),
        ("{company} submitted the bid.", ["company"]),
        ("Merger with {company} approved.", ["company"]),
        ("Vendor: {company}", ["company"]),
        ("Employer: {company}", ["company"]),

        # ===== DATES OF BIRTH =====
        ("Date of birth: {dob}", ["dob"]),
        ("Born on {dob}.", ["dob"]),
        ("DOB: {dob}", ["dob"]),
        ("Patient birthdate {dob}.", ["dob"]),
        ("Date of birth on file: {dob}", ["dob"]),
        ("DOB confirmed as {dob}.", ["dob"]),
        ("Age verified, born {dob}.", ["dob"]),
        ("Birth date {dob} recorded.", ["dob"]),
        ("Member since birth on {dob}.", ["dob"]),
        ("Identity verified, DOB {dob}.", ["dob"]),

        # ===== DRIVER LICENSE =====
        ("Driver license number: {license}", ["license"]),
        ("DL: {license}", ["license"]),
        ("License ID {license} verified.", ["license"]),
        ("State license {license} on file.", ["license"]),
        ("Operator license {license} scanned.", ["license"]),
        ("DL number {license} confirmed.", ["license"]),
        ("Driver ID: {license}", ["license"]),
        ("License plate linked to DL {license}.", ["license"]),
        ("Submitted driver license {license}.", ["license"]),
        ("License {license} expires this year.", ["license"]),

        # ===== PASSPORT =====
        ("Passport number: {passport}", ["passport"]),
        ("Passport {passport} expires next year.", ["passport"]),
        ("Travel document passport {passport}.", ["passport"]),
        ("Visa application attached to passport {passport}.", ["passport"]),
        ("Passport ID: {passport}", ["passport"]),
        ("International travel with passport {passport}.", ["passport"]),
        ("Passport {passport} renewed.", ["passport"]),
        ("Border control scanned passport {passport}.", ["passport"]),

        # ===== IP ADDRESSES =====
        ("Server IP: {ip_address}", ["ip_address"]),
        ("Connect to {ip_address}.", ["ip_address"]),
        ("IP address {ip_address} blocked.", ["ip_address"]),
        ("Login from IP {ip_address}.", ["ip_address"]),
        ("Request origin: {ip_address}", ["ip_address"]),
        ("Firewall blocked {ip_address}.", ["ip_address"]),
        ("Remote host {ip_address} connected.", ["ip_address"]),
        ("Access granted to {ip_address}.", ["ip_address"]),

        # ===== MEDICAL RECORD NUMBERS =====
        ("Medical record number {mrn}.", ["mrn"]),
        ("MRN: {mrn}", ["mrn"]),
        ("Patient MRN {mrn} accessed.", ["mrn"]),
        ("Chart pulled for {mrn}.", ["mrn"]),
        ("Discharge summary for {mrn} filed.", ["mrn"]),
        ("Lab results under {mrn}.", ["mrn"]),
        ("Referral created for patient {mrn}.", ["mrn"]),
        ("Record {mrn} updated in EMR.", ["mrn"]),

        # ===== BANK ACCOUNTS =====
        ("Account number: {bank_account}", ["bank_account"]),
        ("Bank account {bank_account}.", ["bank_account"]),
        ("Transfer to account {bank_account}.", ["bank_account"]),
        ("Direct deposit to {bank_account}.", ["bank_account"]),
        ("ACH routing sent to {bank_account}.", ["bank_account"]),
        ("Savings account: {bank_account}", ["bank_account"]),
        ("Linked bank account {bank_account}.", ["bank_account"]),
        ("Wire transfer to {bank_account} completed.", ["bank_account"]),

        # ===== USERNAMES =====
        ("Username: {username}", ["username"]),
        ("Login as {username}.", ["username"]),
        ("User {username} logged in.", ["username"]),
        ("Account {username} suspended.", ["username"]),
        ("Password reset for {username}.", ["username"]),
        ("Profile: {username}", ["username"]),
        ("Admin user {username} created.", ["username"]),
        ("{username} updated their settings.", ["username"]),
        ("Session started for {username}.", ["username"]),
        ("Two-factor enabled for {username}.", ["username"]),

        # ===== VIN =====
        ("Vehicle VIN: {vin}", ["vin"]),
        ("VIN number {vin} registered.", ["vin"]),
        ("Car with VIN {vin} recalled.", ["vin"]),
        ("Registration for VIN {vin} expired.", ["vin"]),
        ("Insurance linked to VIN {vin}.", ["vin"]),
        ("Odometer reading for {vin}.", ["vin"]),
        ("Title transfer for VIN {vin}.", ["vin"]),
        ("Dealer submitted VIN {vin} for inspection.", ["vin"]),

        # ===== API KEYS =====
        ("API key: {api_key}", ["api_key"]),
        ("Use token {api_key} for authentication.", ["api_key"]),
        ("Secret key {api_key} rotated.", ["api_key"]),
        ("Authorization header: Bearer {api_key}", ["api_key"]),
        ("Service token: {api_key}", ["api_key"]),
        ("Access token issued: {api_key}", ["api_key"]),
        ("API_KEY={api_key}", ["api_key"]),
        ("Revoke key {api_key} immediately.", ["api_key"]),

        # ===== MAC ADDRESSES =====
        ("Device MAC address: {mac_address}", ["mac_address"]),
        ("Hardware address {mac_address} registered.", ["mac_address"]),
        ("MAC {mac_address} blocked on firewall.", ["mac_address"]),
        ("Network card MAC: {mac_address}", ["mac_address"]),
        ("DHCP lease for {mac_address}.", ["mac_address"]),
        ("Access point detected {mac_address}.", ["mac_address"]),

        # ===== EMPLOYEE IDs =====
        ("Employee ID: {emp_id}", ["emp_id"]),
        ("Staff member {emp_id} checked in.", ["emp_id"]),
        ("Payroll for {emp_id} processed.", ["emp_id"]),
        ("Badge {emp_id} deactivated.", ["emp_id"]),
        ("HR file for {emp_id} updated.", ["emp_id"]),
        ("Employee {emp_id} submitted timesheet.", ["emp_id"]),

        # ===== INSURANCE NUMBERS =====
        ("Insurance policy: {insurance}", ["insurance"]),
        ("Policy number {insurance} active.", ["insurance"]),
        ("Claim filed under policy {insurance}.", ["insurance"]),
        ("Coverage verified for {insurance}.", ["insurance"]),
        ("Renewal notice for policy {insurance}.", ["insurance"]),
        ("Premium for {insurance} due.", ["insurance"]),

        # ===== MIXED/COMPLEX PATTERNS =====
        ("{name} lives at {address}.", ["name", "address"]),
        ("Contact {name} at {email} or {phone_number}.", ["name", "email", "phone_number"]),
        ("{name} from {company} called from {phone_number}.", ["name", "company", "phone_number"]),
        ("Patient {name}, DOB {dob}, SSN {ssn}.", ["name", "dob", "ssn"]),
        ("{name} works at {company} and can be reached at {email}.", ["name", "company", "email"]),
        ("User {username} logged in from IP {ip_address}.", ["username", "ip_address"]),
        ("Vehicle VIN {vin} owned by {name}.", ["vin", "name"]),
        ("Employee {emp_id} {name} has email {email}.", ["emp_id", "name", "email"]),
        
        # ===== NEGATIVE SAMPLES (No PII) - CRITICAL! =====
        ("Hello world.", []),
        ("This is a test sentence.", []),
        ("No sensitive information here.", []),
        ("The weather is nice today.", []),
        ("The rose is red.", []),
        ("I like to walk in the park.", []),
        ("The company is doing well.", []),
        ("Please update the record.", []),
        ("Call me later.", []),
        ("The project deadline is next week.", []),
        ("We need to schedule a meeting.", []),
        ("The report is ready for review.", []),
        ("Please send the document soon.", []),
        ("Thank you for your time.", []),
        ("The system is working correctly.", []),
        ("Data processing completed successfully.", []),
        ("No errors found in the log.", []),
        ("Customer service is available 24/7.", []),
        ("Personal information should be protected.", []),
        ("Contact information has been updated.", []),
        ("Financial records are confidential.", []),
        ("Do not distribute this document.", []),
        ("Confidential customer database.", []),
        ("Record number assigned.", []),
        ("Employee benefits program.", []),
        ("Medical information protected.", []),
        ("Banking services available.", []),
        ("Credit card payments accepted.", []),
        ("Social Security Administration office.", []),
        ("Email verification required.", []),
        ("Phone support available.", []),
        ("The annual revenue increased.", []),
        ("Department of Human Resources.", []),
        ("Information Technology services.", []),
        ("Corporate headquarters location.", []),
        ("Business development strategy.", []),
        ("Quality assurance testing.", []),
        ("Project management office.", []),
        ("Customer relationship management.", []),
        ("Network security protocols.", []),
        ("Database administration tasks.", []),
        ("Software development lifecycle.", []),
        ("User experience design.", []),
        ("Technical support team.", []),
        ("Research and development.", []),
        ("Sales and marketing division.", []),
        ("Financial planning analysis.", []),
        ("Legal compliance review.", []),
        ("Supply chain management.", []),
        ("Operations and logistics.", []),
        ("Training and development.", []),
        ("Performance evaluation.", []),
        ("Risk management assessment.", []),
        ("Strategic planning session.", []),
        ("Budget allocation process.", []),
        ("Inventory control system.", []),
        ("Production scheduling.", []),
        ("Maintenance procedures.", []),
        ("Safety regulations.", []),
        ("Environmental compliance.", []),
        ("Data analytics platform.", []),
        ("Cloud infrastructure.", []),
        ("Mobile application development.", []),
        ("Artificial intelligence research.", []),
        ("Machine learning models.", []),
        ("Natural language processing.", []),
        ("Computer vision systems.", []),
        ("Blockchain technology.", []),
        ("Internet of things.", []),
        ("Cybersecurity measures.", []),
    ]

    for _ in tqdm(range(count), desc="Generating data"):
        template, _ = random.choice(templates)
        parts = re.split(r'(\{\w+\})', template)
        final_text = ""
        entities = []

        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                key = part[1:-1]
                val = make_value(key)
                label = KEY_TO_LABEL.get(key, "PII")
                start = len(final_text)
                final_text += val
                entities.append((start, start + len(val), label))
            else:
                final_text += part

        data.append({"text": final_text, "entities": entities})

    # Save to JSON
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Generated {count} samples to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", type=str, default="data/train_data.json")
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    generate_data(args.count, args.output)
