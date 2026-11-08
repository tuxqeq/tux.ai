"""
prepare_external.py — build external test sets for eval/eval_detector.py.

Sources (--source):
  nemotron    nvidia/Nemotron-PII test split (default; described below)
  ai4privacy  ai4privacy/pii-masking-300k, English validation file (OpenPII); synthetic, a third
              independent generator. Licence "other": academic use with citation. Needed because
              Nemotron-PII train documents are used to train pii_model_v4.

Source: nvidia/Nemotron-PII (CC BY 4.0), test split. Synthetic US documents from 50+ industries,
structured and unstructured, generated with NVIDIA NeMo Data Designer; character-offset spans.
Cite: Steier, Manoel, Haushalter, Van Segbroeck (2025). Nemotron-PII: Synthesized Data for
Privacy-Preserving AI. NVIDIA. https://huggingface.co/datasets/nvidia/Nemotron-PII

Label handling (each source label goes to exactly one bucket):
  our label  in-scope PII with a type in our scheme (PER, LOC, EMAIL, ...)
  OTHER      PII without a type in our scheme (license plate, URL, password, ...): counts in the
             privacy metrics, not in typed F1
  IGNORE     not an identifier (blood type, religion, a plain date, ...): written to "ignore",
             predictions there are not counted as errors
Unknown labels default to OTHER and are flagged "review" in the printed inventory.
Geography follows HIPAA Safe Harbor: units smaller than a state are identifiers. A LOC span made
only of state and/or country parts ("licensed in California") goes to "ignore"; inside a full
address the state and country stay part of the LOC span.
Spans whose offsets do not match their text are relocated to the nearest occurrence of that text.
Adjacent gold spans with the same mapped label, separated only by spaces/commas, are merged
(first_name + last_name -> one PER; street + city + state + postcode -> one LOC), because the
detector marks a full name or a full address as one span.

Usage (on the Mac, needs internet):
  .venv/bin/python eval/prepare_external.py                  # 1000 docs, seed 7
  .venv/bin/python eval/prepare_external.py --n 2000 --seed 11
Output: data/external_nemotron_test_<n>.json and data/external_nemotron_labels.json
"""
import argparse
import ast
import json
import os
import random
import re
from collections import Counter

TO_OURS = {
    # PER
    "first_name": "PER", "last_name": "PER", "middle_name": "PER", "name": "PER",
    "full_name": "PER", "person_name": "PER", "nickname": "PER",
    # LOC
    "street_address": "LOC", "address": "LOC", "city": "LOC", "state": "LOC", "county": "LOC",
    "country": "LOC", "postcode": "LOC", "zipcode": "LOC", "zip_code": "LOC", "postal_code": "LOC",
    # ORG
    "company_name": "ORG", "organization": "ORG", "organization_name": "ORG", "employer": "ORG",
    # contact
    "email": "EMAIL", "email_address": "EMAIL",
    "phone_number": "PHONE", "phone": "PHONE", "fax_number": "PHONE",
    # government / financial / medical ids
    "ssn": "SSN", "social_security_number": "SSN",
    "credit_debit_card": "CREDIT_CARD", "credit_card_number": "CREDIT_CARD", "card_number": "CREDIT_CARD",
    "date_of_birth": "DOB", "dob": "DOB", "birth_date": "DOB",
    "driver_license": "LICENSE", "driver_license_number": "LICENSE", "drivers_license_number": "LICENSE",
    "passport_number": "PASSPORT",
    "ipv4": "IP_ADDRESS", "ipv6": "IP_ADDRESS", "ip_address": "IP_ADDRESS",
    "medical_record_number": "MRN",
    "account_number": "BANK_ACCOUNT", "bank_account_number": "BANK_ACCOUNT",
    "user_name": "USERNAME", "username": "USERNAME",
    "vehicle_identifier": "VIN", "vin": "VIN",
    "api_key": "API_KEY",
    "mac_address": "MAC",
    "employee_id": "EMP_ID",
    "health_plan_beneficiary_number": "INSURANCE", "insurance_policy_number": "INSURANCE",
    "policy_number": "INSURANCE",
}
OTHER = {  # identifiers without a type in our scheme
    "url", "customer_id", "biometric_identifier", "coordinate", "pin", "password", "cvv",
    "http_cookie", "license_plate", "certificate_license_number", "national_id",
    "device_identifier", "unique_id", "tax_id",
}
IGNORE = {
    "bank_routing_number", "swift_bic",  # identify a bank, not a person
    "blood_type", "race_ethnicity", "religious_belief", "sexuality", "sexual_orientation",
    "political_view", "gender", "sex", "age", "occupation", "job_title", "education_level",
    "language", "date", "time", "date_time", "employment_status", "marital_status",
}
# ai4privacy pii-masking-300k OpenPII labels (unknown labels -> OTHER, flagged "review")
A4P_TO_OURS = {
    "GIVENNAME1": "PER", "GIVENNAME2": "PER", "LASTNAME1": "PER", "LASTNAME2": "PER", "LASTNAME3": "PER",
    "STREET": "LOC", "BUILDING": "LOC", "CITY": "LOC", "POSTCODE": "LOC", "SECADDRESS": "LOC",
    "STATE": "LOC", "COUNTRY": "LOC",
    "EMAIL": "EMAIL", "TEL": "PHONE", "SOCIALNUMBER": "SSN", "BOD": "DOB", "IP": "IP_ADDRESS",
    "DRIVERLICENSE": "LICENSE", "PASSPORT": "PASSPORT", "USERNAME": "USERNAME",
}
A4P_OTHER = {"IDCARD", "PASS", "GEOCOORD"}
A4P_IGNORE = {"TITLE", "SEX", "DATE", "TIME", "CARDISSUER"}

SCHEMES = {
    "nemotron": {"to_ours": None, "other": None, "ignore": None, "state_country": {"state", "country"}},
    "ai4privacy": {"to_ours": A4P_TO_OURS, "other": A4P_OTHER, "ignore": A4P_IGNORE,
                   "state_country": {"STATE", "COUNTRY"}},
}

_MERGE_GAP = re.compile(r"^[\s,]{0,3}$")


def parse_spans(raw):
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return ast.literal_eval(raw)


def bucket(label: str, scheme: str = "nemotron"):
    sc = SCHEMES[scheme]
    to_ours, other, ignore = sc["to_ours"] or TO_OURS, sc["other"] or OTHER, sc["ignore"] or IGNORE
    if label in to_ours:
        return to_ours[label], True
    if label in ignore:
        return "IGNORE", True
    return "OTHER", label in other


_STATE_COUNTRY = {"state", "country"}
RELOCATED_EXAMPLES = []


def locate(text, sp, stats):
    """Return (start, end) of the span; relocate to the nearest occurrence of its text if needed."""
    s, e = int(sp["start"]), int(sp["end"])
    value = sp.get("text", sp.get("value"))
    valid = 0 <= s < e <= len(text)
    if value is not None and not isinstance(value, str):
        # numeric span text (e.g. a PIN stored as int): trust the offsets when they are valid
        stats["nonstring_text"] += 1
        if valid:
            return s, e
        value = str(value)
    if valid and (value is None or text[s:e] == value):
        return s, e
    if value:
        hits = [m.start() for m in re.finditer(re.escape(value), text)]
        if hits:
            best = min(hits, key=lambda h: abs(h - s))
            stats["relocated"] += 1
            if len(RELOCATED_EXAMPLES) < 15:
                RELOCATED_EXAMPLES.append({"label": sp.get("label"), "text": value,
                                           "at_given_offsets": text[s:e] if valid else None,
                                           "shift": best - s})
            return best, best + len(value)
    stats["bad_offsets_dropped"] += 1
    return None


def convert(text, spans, stats, scheme: str = "nemotron"):
    located = []
    for sp in spans:
        pos = locate(text, sp, stats)
        if pos:
            located.append((pos[0], pos[1], str(sp["label"])))
    kept = []
    for s, e, label in sorted(located, key=lambda x: (x[0], -(x[1] - x[0]))):
        if kept and s < kept[-1][1]:
            stats["nested_dropped"] += 1
            continue
        kept.append((s, e, label))
    gold, ignore, parts = [], [], []
    for s, e, label in kept:
        b, _ = bucket(label, scheme)
        if b == "IGNORE":
            ignore.append([s, e, label])
            continue
        if gold and gold[-1][2] == b and _MERGE_GAP.match(text[gold[-1][1]:s]):
            gold[-1][1] = e
            parts[-1].add(label)
            stats["merged"] += 1
        else:
            gold.append([s, e, b])
            parts.append({label})
    final = []
    for g, src in zip(gold, parts):
        if g[2] == "LOC" and src <= SCHEMES[scheme]["state_country"]:  # HIPAA Safe Harbor: state/country alone
            ignore.append([g[0], g[1], "+".join(sorted(src))])
            stats["state_country_ignored"] += 1
        else:
            final.append(g)
    return final, sorted(ignore)


def load_rows(source, split, n, seed):
    """Return (rows, total) with rows = [(text, spans, meta)] sampled with the seed."""
    if source == "nemotron":
        from datasets import load_dataset
        ds = load_dataset("nvidia/Nemotron-PII", split=split)
        print(f"Nemotron-PII {split}: {len(ds)} documents; columns: {ds.column_names}")
        idx = sorted(random.Random(seed).sample(range(len(ds)), min(n, len(ds))))
        rows = []
        for i in idx:
            r = ds[i]
            rows.append((r["text"], parse_spans(r["spans"]),
                         {"uid": r.get("uid"), "domain": r.get("domain"), "document_type": r.get("document_type"),
                          "document_format": r.get("document_format")}))
        return rows, len(ds)
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("ai4privacy/pii-masking-300k", repo_type="dataset",
                           filename="data/validation/1english_openpii_8k.jsonl")
    allrows = [json.loads(line) for line in open(path)]
    allrows = [r for r in allrows if str(r.get("language", "English")).lower().startswith("en")]
    print(f"ai4privacy pii-masking-300k English validation: {len(allrows)} rows; keys: {list(allrows[0].keys())}")
    idx = sorted(random.Random(seed).sample(range(len(allrows)), min(n, len(allrows))))
    return [(allrows[i]["source_text"], parse_spans(allrows[i]["privacy_mask"]), {"id": allrows[i].get("id")})
            for i in idx], len(allrows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["nemotron", "ai4privacy"], default="nemotron")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--split", default="test", help="Nemotron split (ai4privacy: always English validation)")
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    rows, _ = load_rows(args.source, args.split, args.n, args.seed)
    inventory, stats, out = Counter(), Counter(), []
    for text, spans, meta in rows:
        inventory.update(str(sp["label"]) for sp in spans)
        gold, ignore = convert(text, spans, stats, args.source)
        out.append({"text": text, "entities": gold, "ignore": ignore, **meta})

    os.makedirs(args.out_dir, exist_ok=True)
    name = f"external_nemotron_{args.split}_{len(out)}" if args.source == "nemotron" else f"external_ai4privacy_en_{len(out)}"
    path = os.path.join(args.out_dir, name + ".json")
    json.dump(out, open(path, "w"), ensure_ascii=False)
    labels = {lab: {"count": c, "bucket": bucket(lab, args.source)[0], "known": bucket(lab, args.source)[1]}
              for lab, c in inventory.most_common()}
    json.dump({"source": args.source, "split": args.split, "n_docs": len(out), "seed": args.seed,
               "labels": labels, "stats": dict(stats), "relocated_examples": RELOCATED_EXAMPLES},
              open(os.path.join(args.out_dir, f"external_{args.source}_labels.json"), "w"), indent=2)

    words = [len(x["text"].split()) for x in out]
    ents = Counter(e[2] for x in out for e in x["entities"])
    print(f"\nWrote {path}: {len(out)} docs, words/doc mean {sum(words) / len(words):.0f}, max {max(words)}")
    print(f"gold entities: {dict(ents.most_common())}")
    print(f"stats: {dict(stats)}")
    print(f"\n{'source label':<34}{'count':>7}  bucket")
    for lab, info in labels.items():
        print(f"{lab:<34}{info['count']:>7}  {info['bucket']}{'' if info['known'] else '   <- review'}")


if __name__ == "__main__":
    main()
