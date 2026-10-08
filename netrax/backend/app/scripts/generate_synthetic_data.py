"""
NETRA-X Synthetic Data Generator
Generates synthetic investigation documents for testing and demonstration.

ALL DATA IS FICTIONAL — no real persons, cases, or criminal records are used.

SYNTHETIC DEMO DATA — FOR TESTING PURPOSES ONLY
"""

import os
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta

# Try to import fitz for PDF generation; fall back to text if unavailable
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ─── Fictional Entity Pool ────────────────────────────────────────────────
# These names, numbers, and locations are entirely fictional.

PERSONS = [
    "Rahul Sharma", "Amit Verma", "Neha Singh", "Priya Patel",
    "Vikram Malhotra", "Sunita Reddy", "Deepak Gupta", "Kavita Joshi",
    "Rajesh Kumar", "Meena Agarwal", "Suresh Yadav", "Anita Chauhan",
    "Manoj Tiwari", "Pooja Mehta", "Arjun Nair",
]

PHONES = [
    "9876543210", "9988776655", "8877665544", "7766554433",
    "9123456780", "8234567890", "7345678901", "9456789012",
    "8567890123", "9678901234",
]

LOCATIONS = [
    "Station Road", "MG Road", "Gandhi Nagar", "Civil Lines",
    "Rajendra Place", "Nehru Colony", "Subhash Chowk", "Laxmi Nagar",
    "Sector 21", "Industrial Area Phase 2", "Old Bus Stand",
    "Railway Station", "Central Market", "Ring Road", "Highway NH-6",
]

ORGANIZATIONS = [
    "ABC Trading Co.", "XYZ Enterprises", "Global Finance Ltd.",
    "Metro Logistics", "Sunrise Industries", "National Services",
    "Diamond Exports", "City Transport Corp.",
]

VEHICLES = [
    "CG10AB1234", "MP09CD5678", "DL01EF9012", "MH12GH3456",
    "RJ14JK7890", "UP32LM2345", "HR26NP6789", "KA05QR0123",
]

EMAILS = [
    "rahul.sharma@email.com", "amit.verma@mail.co.in",
    "neha.singh@webmail.com", "priya.patel@inbox.net",
    "vikram.m@business.org", "deepak.gupta@service.com",
]

ACCOUNTS = [
    "1234567890123", "9876543210987", "5678901234567",
    "3456789012345", "7890123456789",
]

IMEIS = [
    "123456789012345", "987654321098765", "567890123456789",
    "345678901234567",
]

POLICE_STATIONS = [
    "Central Station", "South Station", "North Station",
    "East Station", "Cyber Crime Cell",
]


def _generate_fir_text(fir_num: int, seed_persons: list[str]) -> str:
    """Generate a synthetic FIR document text."""
    fir_number = f"NX-{fir_num:03d}/2026"
    station = random.choice(POLICE_STATIONS)
    date = (datetime(2026, 1, 1) + timedelta(days=random.randint(0, 270))).strftime("%d/%m/%Y")
    time = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}"

    complainant = seed_persons[0]
    accused = seed_persons[1:]
    location = random.choice(LOCATIONS)
    phone1 = random.choice(PHONES)
    phone2 = random.choice(PHONES)
    vehicle = random.choice(VEHICLES)
    org = random.choice(ORGANIZATIONS)
    email = random.choice(EMAILS)

    text = f"""SYNTHETIC DEMO DATA — FOR TESTING PURPOSES ONLY
ALL NAMES, NUMBERS, AND DETAILS ARE ENTIRELY FICTIONAL

═══════════════════════════════════════════════════════════
                    FIRST INFORMATION REPORT
═══════════════════════════════════════════════════════════

FIR Number: {fir_number}
Police Station: {station}
District: Central District
State: Demo State

Date of Report: {date}
Time of Report: {time}

═══════════════════════════════════════════════════════════
SECTION I — COMPLAINANT DETAILS
═══════════════════════════════════════════════════════════

Name: {complainant}
Phone: {phone1}
Email: {email}
Address: House No. 42, {location}, Central District

═══════════════════════════════════════════════════════════
SECTION II — PERSONS MENTIONED / ACCUSED
═══════════════════════════════════════════════════════════

"""
    for i, person in enumerate(accused, 1):
        acc_phone = random.choice(PHONES)
        text += f"""Accused {i}:
  Name: {person}
  Phone: {acc_phone}
  Address: Near {random.choice(LOCATIONS)}, Central District

"""

    text += f"""═══════════════════════════════════════════════════════════
SECTION III — INCIDENT DETAILS
═══════════════════════════════════════════════════════════

Date of Incident: {date}
Time of Incident: Approximately {time} hours
Location: {location}, near {random.choice(LOCATIONS)}

Vehicle Involved: {vehicle}
Organization Mentioned: {org}

═══════════════════════════════════════════════════════════
SECTION IV — NARRATIVE
═══════════════════════════════════════════════════════════

On {date} at approximately {time} hours, the complainant {complainant}
(phone: {phone1}) reported the following incident at {station}:

The complainant stated that on the above date, while present near {location},
they observed suspicious activity involving the accused {accused[0]}
(contact number: {phone2}). The accused was seen operating from a vehicle
bearing registration number {vehicle}.

"""
    if len(accused) > 1:
        text += f"""The complainant further stated that {accused[0]} was in contact with
{accused[1]} who is believed to be associated with {org}. Multiple phone
calls were exchanged between the parties on numbers {phone1} and {phone2}.

The accused {accused[0]} was seen near {random.choice(LOCATIONS)} and later
near {location} during the period in question.

"""

    if len(accused) > 2:
        text += f"""Investigation also revealed that {accused[2]} was present at the scene
and was communicating via email at {random.choice(EMAILS)}.
An IMEI number {random.choice(IMEIS)} was recovered from device records.
Account number {random.choice(ACCOUNTS)} was found linked to transactions.

"""

    text += f"""═══════════════════════════════════════════════════════════
SECTION V — EVIDENCE COLLECTED
═══════════════════════════════════════════════════════════

1. CCTV footage from {location}
2. Call records from number {phone1}
3. Call records from number {phone2}
4. Vehicle registration details for {vehicle}
5. Bank account records for Account No. {random.choice(ACCOUNTS)}

═══════════════════════════════════════════════════════════
SECTION VI — ACTION TAKEN
═══════════════════════════════════════════════════════════

FIR registered under appropriate sections. Investigation initiated.
The above report was written based on the statement of {complainant}.

Investigating Officer: IO-{random.randint(100, 999)}
Signature: [Signed]
Date: {date}

═══════════════════════════════════════════════════════════
            SYNTHETIC DATA — NOT A REAL DOCUMENT
═══════════════════════════════════════════════════════════
"""
    return text


def _create_pdf(text: str, filepath: str):
    """Create a PDF file from text content."""
    if HAS_FITZ:
        doc = fitz.open()
        # Split text into pages (roughly 3000 chars per page)
        lines = text.split('\n')
        page_lines = []
        current_page_text = ""

        for line in lines:
            test_text = current_page_text + line + "\n"
            if len(test_text) > 3000:
                page_lines.append(current_page_text)
                current_page_text = line + "\n"
            else:
                current_page_text = test_text

        if current_page_text:
            page_lines.append(current_page_text)

        for page_text in page_lines:
            page = doc.new_page(width=595, height=842)  # A4
            text_rect = fitz.Rect(50, 50, 545, 792)
            page.insert_textbox(
                text_rect,
                page_text,
                fontsize=10,
                fontname="helv",
            )

        doc.save(filepath)
        doc.close()
    else:
        # Fallback: save as text file with .pdf extension
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)


def _generate_cdr_csv(filepath: str, persons: list[str], phones: list[str]):
    """Generate a synthetic Call Detail Record CSV."""
    headers = [
        "record_id", "calling_number", "called_number", "call_date",
        "call_time", "duration_seconds", "call_type", "cell_tower_id",
        "cell_tower_location", "imei"
    ]

    rows = []
    base_date = datetime(2026, 6, 1)

    for i in range(50):
        caller = random.choice(phones[:5])
        called = random.choice(phones[3:])
        call_date = (base_date + timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d")
        call_time = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
        duration = random.randint(5, 1800)
        call_type = random.choice(["OUTGOING", "INCOMING", "MISSED"])
        tower_id = f"TOWER-{random.randint(100, 999)}"
        tower_loc = random.choice(LOCATIONS)
        imei = random.choice(IMEIS)

        rows.append([
            f"CDR-{i + 1:05d}", caller, called, call_date, call_time,
            str(duration), call_type, tower_id, tower_loc, imei
        ])

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DEMO DATA — FOR TESTING PURPOSES ONLY\n")
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _generate_financial_csv(filepath: str, persons: list[str]):
    """Generate a synthetic financial transaction CSV."""
    headers = [
        "transaction_id", "date", "account_from", "account_to",
        "amount", "currency", "description", "beneficiary_name",
        "bank_name", "status"
    ]

    rows = []
    base_date = datetime(2026, 3, 1)

    for i in range(30):
        txn_date = (base_date + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%d")
        acc_from = random.choice(ACCOUNTS)
        acc_to = random.choice(ACCOUNTS)
        amount = round(random.uniform(500, 500000), 2)
        person = random.choice(persons[:8])
        bank = random.choice(["State Bank", "National Bank", "City Bank", "Metro Bank"])
        desc = random.choice([
            "Wire Transfer", "Online Payment", "Cash Deposit",
            "ATM Withdrawal", "NEFT Transfer", "UPI Payment"
        ])

        rows.append([
            f"TXN-{i + 1:06d}", txn_date, acc_from, acc_to,
            f"{amount:.2f}", "INR", desc, person, bank,
            random.choice(["COMPLETED", "PENDING", "FAILED"])
        ])

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DEMO DATA — FOR TESTING PURPOSES ONLY\n")
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def generate_all_synthetic_data(output_dir: str = "data/synthetic"):
    """Generate all synthetic test data files."""
    output_path = Path(output_dir)

    # Create directories
    (output_path / "fir").mkdir(parents=True, exist_ok=True)
    (output_path / "cdr").mkdir(parents=True, exist_ok=True)
    (output_path / "financial").mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  NETRA-X Synthetic Data Generator")
    print("  ALL DATA IS FICTIONAL — FOR TESTING ONLY")
    print("=" * 60)

    # Generate 5 FIRs with overlapping persons for Phase 2 testing
    fir_person_sets = [
        ["Rahul Sharma", "Amit Verma", "Neha Singh"],
        ["Amit Verma", "Priya Patel", "Vikram Malhotra"],
        ["Deepak Gupta", "Neha Singh", "Kavita Joshi"],
        ["Vikram Malhotra", "Rajesh Kumar", "Sunita Reddy", "Meena Agarwal"],
        ["Rahul Sharma", "Deepak Gupta", "Arjun Nair"],
    ]

    for i, persons in enumerate(fir_person_sets, 1):
        fir_text = _generate_fir_text(i, persons)
        filepath = str(output_path / "fir" / f"FIR_{i:03d}.pdf")
        _create_pdf(fir_text, filepath)
        print(f"  ✓ Generated {filepath}")

    # Also create a TXT version of FIR 1 for testing
    fir1_text = _generate_fir_text(1, fir_person_sets[0])
    txt_path = str(output_path / "fir" / "FIR_001.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(fir1_text)
    print(f"  ✓ Generated {txt_path}")

    # Generate 2 CDR files
    for i in range(1, 3):
        filepath = str(output_path / "cdr" / f"CDR_{i:03d}.csv")
        _generate_cdr_csv(filepath, PERSONS, PHONES)
        print(f"  ✓ Generated {filepath}")

    # Generate 2 financial files
    for i in range(1, 3):
        filepath = str(output_path / "financial" / f"transactions_{i:03d}.csv")
        _generate_financial_csv(filepath, PERSONS)
        print(f"  ✓ Generated {filepath}")

    print()
    print(f"  Total files generated: 10")
    print(f"  Output directory: {output_path.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_synthetic_data()
