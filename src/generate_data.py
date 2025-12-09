import argparse
import json
import random
from faker import Faker
from tqdm import tqdm
import os

def generate_data(count, output_file):
    fake = Faker()
    data = []
    
    # Define templates with placeholders for PII
    # Comprehensive templates covering many PII types and contexts
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
        
        # ===== PHONE NUMBERS =====
        ("Call me at {phone_number}.", ["phone_number"]),
        ("My phone number is {phone_number}.", ["phone_number"]),
        ("You can reach me at {phone_number}.", ["phone_number"]),
        ("Contact number: {phone_number}", ["phone_number"]),
        ("Call {phone_number} for support.", ["phone_number"]),
        ("Mobile: {phone_number}", ["phone_number"]),
        ("Office phone: {phone_number}", ["phone_number"]),
        
        # ===== SSN =====
        ("His SSN is {ssn}.", ["ssn"]),
        ("Social Security Number: {ssn}", ["ssn"]),
        ("Patient SSN {ssn} was verified.", ["ssn"]),
        ("SSN on file: {ssn}", ["ssn"]),
        ("Tax ID {ssn} confirmed.", ["ssn"]),
        
        # ===== CREDIT CARDS =====
        ("My credit card number is {credit_card_number}.", ["credit_card_number"]),
        ("Card ending in {credit_card_number}.", ["credit_card_number"]),
        ("Payment via card {credit_card_number}.", ["credit_card_number"]),
        ("Credit card {credit_card_number} authorized.", ["credit_card_number"]),
        ("Charge to card {credit_card_number}.", ["credit_card_number"]),
        
        # ===== ADDRESSES =====
        ("I live at {address}.", ["address"]),
        ("Send the package to {address}.", ["address"]),
        ("Delivery address: {address}", ["address"]),
        ("Mailing address is {address}.", ["address"]),
        ("Shipping to {address}.", ["address"]),
        ("Office located at {address}.", ["address"]),
        
        # ===== COMPANIES/ORGANIZATIONS =====
        ("I work at {company}.", ["company"]),
        ("{company} announced new policies today.", ["company"]),
        ("The contract with {company} was signed.", ["company"]),
        ("Partnership with {company} established.", ["company"]),
        ("{company} is our main client.", ["company"]),
        
        # ===== DATES OF BIRTH =====
        ("Date of birth: {dob}", ["dob"]),
        ("Born on {dob}.", ["dob"]),
        ("DOB: {dob}", ["dob"]),
        ("Patient birthdate {dob}.", ["dob"]),
        
        # ===== DRIVER LICENSE =====
        ("Driver license number: {license}", ["license"]),
        ("DL: {license}", ["license"]),
        ("License ID {license} verified.", ["license"]),
        
        # ===== PASSPORT =====
        ("Passport number: {passport}", ["passport"]),
        ("Passport {passport} expires next year.", ["passport"]),
        
        # ===== IP ADDRESSES =====
        ("Server IP: {ip_address}", ["ip_address"]),
        ("Connect to {ip_address}.", ["ip_address"]),
        ("IP address {ip_address} blocked.", ["ip_address"]),
        
        # ===== MEDICAL RECORD NUMBERS =====
        ("Medical record number {mrn}.", ["mrn"]),
        ("MRN: {mrn}", ["mrn"]),
        ("Patient MRN {mrn} accessed.", ["mrn"]),
        
        # ===== BANK ACCOUNTS =====
        ("Account number: {bank_account}", ["bank_account"]),
        ("Bank account {bank_account}.", ["bank_account"]),
        ("Transfer to account {bank_account}.", ["bank_account"]),
        
        # ===== USERNAMES =====
        ("Username: {username}", ["username"]),
        ("Login as {username}.", ["username"]),
        ("User {username} logged in.", ["username"]),
        
        # ===== MIXED/COMPLEX PATTERNS =====
        ("{name} lives at {address}.", ["name", "address"]),
        ("Contact {name} at {email} or {phone_number}.", ["name", "email", "phone_number"]),
        ("{name} from {company} called from {phone_number}.", ["name", "company", "phone_number"]),
        ("Patient {name}, DOB {dob}, SSN {ssn}.", ["name", "dob", "ssn"]),
        ("{name} works at {company} and can be reached at {email}.", ["name", "company", "email"]),
        
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
        template, pii_types = random.choice(templates)
        
        # Generate PII values
        pii_values = {}
        entities = []
        
        text = template
        
        # We need to construct the text and track entity indices
        # This is a simplified approach. For robust NER, we need exact character offsets.
        # Let's build the string and track offsets.
        
        current_text = ""
        last_idx = 0
        
        # Split template by placeholders to reconstruct and find offsets
        # This is tricky with multiple placeholders.
        # Alternative: Use format and then search? Searching might be ambiguous if value appears twice.
        # Better: Construct piece by piece.
        
        # Simple approach for this proof of concept:
        # 1. Generate values
        # 2. Format string
        # 3. Find offsets (assuming uniqueness for simplicity in this POC, or careful construction)
        
        # Let's try a safer construction method
        # We will iterate through the template string and replace placeholders one by one
        
        formatted_text = text
        temp_entities = []
        
        for pii_type in pii_types:
            if pii_type == "name":
                val = fake.name()
            elif pii_type == "email":
                val = fake.email()
            elif pii_type == "email_obfuscated":
                val = fake.email().replace("@", " at ").replace(".", " dot ")
            elif pii_type == "address":
                val = fake.address().replace("\n", ", ")
            elif pii_type == "phone_number":
                val = fake.phone_number()
            elif pii_type == "phone_number_text":
                # Simple simulation of text phone number
                val = "five five five, one two three four" 
            elif pii_type == "phone_number_obfuscated":
                val = "555 dot 1234"
            elif pii_type == "credit_card_number":
                val = fake.credit_card_number()
            elif pii_type == "ssn":
                val = fake.ssn()
            elif pii_type == "company":
                val = fake.company()
            else:
                val = "UNKNOWN"
            
            # Placeholder format
            placeholder = "{" + pii_type + "}"
            
            # Find position of placeholder
            start_index = formatted_text.find(placeholder)
            if start_index != -1:
                # Replace placeholder with value
                formatted_text = formatted_text.replace(placeholder, val, 1)
                end_index = start_index + len(val)
                
                # Map PII type to NER label (simplified)
                # Map PII type to NER label (simplified)
                label = "PER" if pii_type == "name" else \
                        "LOC" if pii_type == "address" else \
                        "ORG" if pii_type == "company" else \
                        "PII" # Default for others (email, phone, ssn, cc)
                
                temp_entities.append({
                    "start": start_index,
                    "end": end_index,
                    "label": label,
                    "text": val
                })
                
                # Adjust positions of subsequent entities if we had them (but we are replacing one by one)
                # Wait, if we replace {name} with "John Doe", the string length changes.
                # If we have multiple placeholders, subsequent ones shift.
                # But we are finding the placeholder in the *current* formatted_text.
                # The issue is if we have already recorded entities, their offsets might shift?
                # No, because we haven't recorded them yet.
                # BUT, if we have multiple placeholders, we need to process them left-to-right to keep indices valid?
                # Or we can just rebuild the string.
                pass
        
        # Re-doing the construction to be robust against multiple entities
        # We can't easily track offsets if we just use .replace() repeatedly without care.
        # Let's use a different strategy: Tokenize the template?
        
        # Strategy 2: Build from parts
        # "The invoice was sent to {name} at {email}."
        # Parts: ["The invoice was sent to ", "{name}", " at ", "{email}", "."]
        
        # Let's stick to the template list but make it a list of parts
        # For simplicity in this script, let's just handle single PII or simple cases.
        # Or better, use a library or just careful string manipulation.
        
        # Let's use the .format() approach but with unique markers, then replace markers?
        # Actually, for a training script, we need BIO tags on tokens.
        # So maybe we should generate word-by-word?
        
        # Let's go with a simpler approach:
        # Generate the text and the entities.
        # For the purpose of this task, let's keep it simple.
        
        # Let's just use one PII per sentence for now to avoid overlap/shift issues in this basic script,
        # or handle the multi-PII templates carefully.
        
        # Actually, let's just use the simple replace and find. 
        # It might fail if the generated value is the same as some other word, but unlikely for PII.
        
        # Re-implementing the loop for correctness:
        
        # 1. Identify all placeholders in order
        import re
        placeholders = [m.group(0) for m in re.finditer(r'\{(\w+)\}', template)]
        
        current_text = template
        current_offset_shift = 0
        valid_sample = True
        
        sample_entities = []
        
        # We need to replace them in order of appearance to track offsets correctly?
        # Actually, if we use re.sub with a callback, we can track it.
        
        def replace_callback(match):
            key = match.group(1)
            if key == "name": val = fake.name()
            elif key == "email": val = fake.email()
            elif key == "email_obfuscated": val = fake.email().replace("@", " at ").replace(".", " dot ")
            elif key == "address": val = fake.address().replace("\n", ", ")
            elif key == "phone_number": val = fake.phone_number()
            elif key == "phone_number_text": val = "five five five, one two three four"
            elif key == "phone_number_obfuscated": val = "555 dot 1234"
            elif key == "credit_card_number": val = fake.credit_card_number()
            elif key == "ssn": val = fake.ssn()
            elif key == "company": val = fake.company()
            else: val = "UNKNOWN"
            
            # Determine label
            label = "PER" if key == "name" else \
                    "LOC" if key == "address" else \
                    "ORG" if key == "company" else \
                    "PII"
            
            # We need the start index in the *final* string.
            # This is hard with re.sub.
            
            # Let's just store the value and label, and we'll reconstruct the string manually.
            return f"___{key}___{val}___{label}___"

        # Intermediate step: replace with markers
        # "The invoice was sent to ___name___John Doe___PER___ at ..."
        # This is getting complicated.
        
        # Let's try the simplest robust way:
        # Split by {key}
        parts = re.split(r'(\{\w+\})', template)
        final_text = ""
        entities = []
        
        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                key = part[1:-1]
                if key == "name": val = fake.name()
                elif key == "email": val = fake.email()
                elif key == "address": val = fake.address().replace("\n", ", ")
                elif key == "phone_number": val = fake.phone_number()
                elif key == "credit_card_number": val = fake.credit_card_number()
                elif key == "ssn": val = fake.ssn()
                elif key == "company": val = fake.company()
                elif key == "dob": val = fake.date_of_birth().strftime("%m/%d/%Y")
                elif key == "license": 
                    # Driver license format: State code + random numbers
                    val = f"{fake.random_uppercase_letter()}{fake.random_int(min=1000000, max=9999999)}"
                elif key == "passport": 
                    # US Passport: 9 digits
                    val = str(fake.random_int(min=100000000, max=999999999))
                elif key == "ip_address": val = fake.ipv4()
                elif key == "mrn": 
                    # Medical record number
                    val = f"MRN-{fake.random_int(min=100000, max=999999)}"
                elif key == "bank_account": 
                    val = str(fake.random_int(min=10000000000, max=99999999999))
                elif key == "username": 
                    val = fake.user_name()
                else: val = part  # Should not happen based on templates
                
                # Use specific labels instead of generic "PII"
                label = "PER" if key == "name" else \
                        "LOC" if key == "address" else \
                        "ORG" if key == "company" else \
                        "EMAIL" if key == "email" else \
                        "PHONE" if key == "phone_number" else \
                        "SSN" if key == "ssn" else \
                        "CREDIT_CARD" if key == "credit_card_number" else \
                        "DOB" if key == "dob" else \
                        "LICENSE" if key == "license" else \
                        "PASSPORT" if key == "passport" else \
                        "IP_ADDRESS" if key == "ip_address" else \
                        "MRN" if key == "mrn" else \
                        "BANK_ACCOUNT" if key == "bank_account" else \
                        "USERNAME" if key == "username" else \
                        "PII"  # Fallback for other types
                
                start = len(final_text)
                final_text += val
                end = len(final_text)
                
                entities.append((start, end, label))
            else:
                final_text += part
        
        data.append({
            "text": final_text,
            "entities": entities
        })

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
