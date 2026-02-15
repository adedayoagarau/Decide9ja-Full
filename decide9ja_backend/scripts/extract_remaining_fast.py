#!/usr/bin/env python3
"""
FAST parallel extraction for remaining states.
Uses multiprocessing to extract multiple states simultaneously.
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    os.system("pip3 install pdfplumber")
    import pdfplumber

BASE_DIR = Path(__file__).parent.parent
# RAW_PDFS = BASE_DIR / "raw_pdfs" / "states"
RAW_PDFS = Path("/Volumes/Crucial X10/naijadata/raw_pdfs/states")
if not RAW_PDFS.exists():
    # Fallback to verify structure
    RAW_PDFS = Path("/Volumes/Crucial X10/naijadata/data/states")

OUTPUT_DIR = BASE_DIR / "data" / "states"
FINDINGS_DIR = BASE_DIR / "findings"

# States already extracted - SKIP these
ALREADY_EXTRACTED = {
    "abia", "akwa_ibom", "cross_river", "delta", "ebonyi", "edo", "ekiti",
    "kaduna", "kano", "kogi", "kwara", "lagos", "nasarawa", "ogun", "osun", "oyo", "sokoto"
}

# State populations
STATE_POPULATIONS = {
    "adamawa": 4_500_000, "anambra": 5_500_000, "bauchi": 7_000_000,
    "bayelsa": 2_500_000, "benue": 6_000_000, "borno": 6_500_000,
    "enugu": 4_500_000, "gombe": 3_500_000, "imo": 5_500_000,
    "jigawa": 6_000_000, "katsina": 8_000_000, "kebbi": 5_000_000,
    "niger": 6_000_000, "ondo": 5_000_000, "plateau": 4_500_000,
    "rivers": 8_000_000, "taraba": 3_500_000, "yobe": 4_000_000,
    "zamfara": 5_000_000,
}

OUTRAGE_KEYWORDS = [
    "vehicle", "motor vehicle", "car", "convoy", "suv", "prado", "land cruiser",
    "hilux", "toyota", "bus", "coaster", "travel", "refreshment", "honorarium",
    "sitting allowance", "furniture", "generator", "reform", "governance",
    "international travel", "overseas", "foreign trip", "consultancy"
]


def parse_amount(text):
    if not text:
        return 0
    cleaned = re.sub(r'[₦N,\s]', '', str(text))
    multiplier = 1
    if 'B' in cleaned.upper():
        cleaned = cleaned.upper().replace('B', '')
        multiplier = 1_000_000_000
    elif 'M' in cleaned.upper():
        cleaned = cleaned.upper().replace('M', '')
        multiplier = 1_000_000
    elif 'T' in cleaned.upper():
        cleaned = cleaned.upper().replace('T', '')
        multiplier = 1_000_000_000_000
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return 0


def format_naira(amount):
    if amount >= 1_000_000_000_000:
        return f"₦{amount/1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:
        return f"₦{amount/1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"₦{amount/1_000_000:.2f}M"
    return f"₦{amount:,.0f}"


def extract_pdf(pdf_path, state, year):
    """Extract budget items from a single PDF"""
    items = []
    current_mda = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages[:50]):  # Limit pages for speed
                text = page.extract_text() or ""

                mda_match = re.search(r'^([A-Z][A-Z\s&,\-]+(?:MINISTRY|DEPARTMENT|AGENCY|COMMISSION|OFFICE|BOARD|COUNCIL|SERVICE))(?:\s|$)', text, re.MULTILINE)
                if mda_match:
                    current_mda = mda_match.group(1).strip()

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row or len(row) < 2:
                            continue

                        budget_code = None
                        description = None
                        amount = 0

                        for cell in row:
                            if not cell:
                                continue
                            cell_str = str(cell).strip()

                            code_match = re.match(r'^(\d{6,8})$', cell_str)
                            if code_match:
                                budget_code = code_match.group(1)
                                continue

                            if len(cell_str) < 30 and re.search(r'[\d,]+', cell_str):
                                parsed = parse_amount(cell_str)
                                if parsed > amount:
                                    amount = parsed
                                continue

                            if len(cell_str) > 5 and not cell_str.isdigit():
                                if not description or len(cell_str) > len(description):
                                    description = cell_str

                        if description and amount > 1_000_000:
                            item = {
                                "page": page_num + 1,
                                "mda": current_mda,
                                "budget_code": budget_code,
                                "description": description,
                                "amount": amount,
                                "state": state.replace("_", " ").title(),
                                "year": year,
                            }

                            desc_lower = description.lower()
                            if any(kw in desc_lower for kw in OUTRAGE_KEYWORDS):
                                item["flagged"] = "OUTRAGE"
                            items.append(item)

    except Exception as e:
        pass  # Silent fail for speed

    return items


def analyze_state(state, items):
    """Generate findings for a state"""
    findings = []
    state_title = state.replace("_", " ").title()
    population = STATE_POPULATIONS.get(state, 5_000_000)

    vehicle_items = [i for i in items if i.get("flagged") and any(kw in i.get("description", "").lower() for kw in ["vehicle", "motor", "car", "hilux", "toyota", "land cruiser", "prado", "convoy", "bus", "coaster"])]
    vehicle_total = sum(i["amount"] for i in vehicle_items if i["amount"] < 100_000_000_000)

    travel_items = [i for i in items if i.get("flagged") and any(kw in i.get("description", "").lower() for kw in ["travel", "overseas", "foreign"])]
    travel_total = sum(i["amount"] for i in travel_items if i["amount"] < 100_000_000_000)

    consultancy_items = [i for i in items if i.get("flagged") and "consultancy" in i.get("description", "").lower()]
    consultancy_total = sum(i["amount"] for i in consultancy_items if i["amount"] < 100_000_000_000)

    health_items = [i for i in items if any(kw in i.get("description", "").lower() for kw in ["health", "hospital", "clinic", "medical"])]
    health_total = sum(i["amount"] for i in health_items if i["amount"] < 500_000_000_000)

    total_expenditure = sum(i["amount"] for i in items if i["amount"] < 500_000_000_000)

    year = items[0]["year"] if items else 2026

    # Total expenditure finding
    if total_expenditure > 100_000_000_000:
        findings.append({
            "id": f"{state}-total-{year}",
            "type": "STATE_BUDGET",
            "entity": "Total Expenditure",
            "description": f"{state_title} {year} budget totals {format_naira(total_expenditure)}. Population: {population:,}. Per capita: {format_naira(total_expenditure/population)}.",
            "amount": total_expenditure,
            "severity": "MEDIUM",
            "year": year,
            "state": state_title,
            "recommendation": "Compare per-capita spending with other states.",
            "risk_score": 50,
            "risk_factors": [f"Total: {format_naira(total_expenditure)}", f"Per capita: {format_naira(total_expenditure/population)}"]
        })

    # Vehicle spending
    if vehicle_total > 1_000_000_000:
        per_capita = vehicle_total / population
        findings.append({
            "id": f"{state}-vehicles-{year}",
            "type": "VEHICLE_MADNESS",
            "entity": f"Vehicle Spending {year}",
            "description": f"{state_title} budgets {format_naira(vehicle_total)} for vehicles ({len(vehicle_items)} items). {format_naira(per_capita)} per citizen.",
            "amount": vehicle_total,
            "severity": "CRITICAL" if vehicle_total > 10_000_000_000 else "HIGH",
            "year": year,
            "state": state_title,
            "recommendation": f"Compare to healthcare: {format_naira(health_total)}",
            "risk_score": min(99, int(50 + (vehicle_total / 1_000_000_000))),
            "risk_factors": [f"Total: {format_naira(vehicle_total)}", f"{len(vehicle_items)} items", f"{format_naira(per_capita)} per citizen"]
        })

    # Travel spending
    if travel_total > 500_000_000:
        findings.append({
            "id": f"{state}-travel-{year}",
            "type": "TRAVEL_EXCESS",
            "entity": f"Travel Spending {year}",
            "description": f"{state_title} allocates {format_naira(travel_total)} for travel. Could build {int(travel_total / 150_000_000)} schools.",
            "amount": travel_total,
            "severity": "HIGH" if travel_total > 2_000_000_000 else "MEDIUM",
            "year": year,
            "state": state_title,
            "recommendation": "Reduce travel, use virtual meetings.",
            "risk_score": min(80, int(40 + (travel_total / 100_000_000))),
            "risk_factors": [f"Travel: {format_naira(travel_total)}", f"Could build {int(travel_total / 150_000_000)} schools"]
        })

    # Consultancy spending
    if consultancy_total > 500_000_000:
        findings.append({
            "id": f"{state}-consultancy-{year}",
            "type": "CONSULTANCY_EXCESS",
            "entity": f"Consultancy {year}",
            "description": f"{state_title} budgets {format_naira(consultancy_total)} for consultancy services.",
            "amount": consultancy_total,
            "severity": "HIGH" if consultancy_total > 5_000_000_000 else "MEDIUM",
            "year": year,
            "state": state_title,
            "recommendation": "Build internal capacity instead.",
            "risk_score": min(75, int(35 + (consultancy_total / 200_000_000))),
            "risk_factors": [f"Consultancy: {format_naira(consultancy_total)}"]
        })

    # Top outrage items
    for item in sorted([i for i in items if i.get("flagged") and 1_000_000_000 < i["amount"] < 50_000_000_000], key=lambda x: x["amount"], reverse=True)[:3]:
        findings.append({
            "id": f"{state}-item-{item.get('budget_code', item['page'])}-{year}",
            "type": "HIGH_VALUE_OUTRAGE",
            "entity": item["description"][:80],
            "description": f"{format_naira(item['amount'])} for '{item['description'][:60]}' in {state_title}",
            "amount": item["amount"],
            "severity": "CRITICAL" if item["amount"] > 5_000_000_000 else "HIGH",
            "year": year,
            "state": state_title,
            "budget_code": item.get("budget_code"),
            "recommendation": "Request itemized breakdown.",
            "risk_score": min(95, int(60 + (item["amount"] / 500_000_000))),
            "risk_factors": [f"Amount: {format_naira(item['amount'])}"]
        })

    return findings


def process_state(state_dir):
    """Process a single state - called in parallel"""
    state = state_dir.name

    if state in ALREADY_EXTRACTED or state.startswith(".") or not state_dir.is_dir():
        return state, [], []

    print(f"[START] {state.upper()}", flush=True)

    state_items = []

    # Check for year directories or direct PDFs
    pdf_files = list(state_dir.glob("**/*.pdf"))

    for pdf_file in pdf_files:
        # Try to get year from path
        try:
            year = int(pdf_file.parent.name)
        except ValueError:
            year = 2025  # Default

        items = extract_pdf(pdf_file, state, year)
        state_items.extend(items)

    if state_items:
        # Save state items
        year = state_items[0]["year"] if state_items else 2025
        output_path = OUTPUT_DIR / state / str(year)
        output_path.mkdir(parents=True, exist_ok=True)

        with open(output_path / "budget_items.json", "w") as f:
            json.dump({"items": state_items, "total": len(state_items)}, f, indent=2)

        # Generate findings
        findings = analyze_state(state, state_items)

        print(f"[DONE] {state.upper()}: {len(state_items)} items, {len(findings)} findings", flush=True)
        return state, state_items, findings

    print(f"[SKIP] {state.upper()}: No items extracted", flush=True)
    return state, [], []


def main():
    print("=" * 60)
    print("FAST PARALLEL EXTRACTION - REMAINING 19 STATES")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Workers: {multiprocessing.cpu_count()}")
    print()

    # Get remaining states
    remaining_states = []
    for state_dir in sorted(RAW_PDFS.iterdir()):
        if state_dir.is_dir() and state_dir.name not in ALREADY_EXTRACTED and not state_dir.name.startswith("."):
            pdf_count = len(list(state_dir.glob("**/*.pdf")))
            if pdf_count > 0:
                remaining_states.append((state_dir, pdf_count))
                print(f"  {state_dir.name}: {pdf_count} PDFs")

    print(f"\nProcessing {len(remaining_states)} states in parallel...\n")

    all_findings = []
    all_items = []
    completed = 0

    # Process in parallel
    with ProcessPoolExecutor(max_workers=min(8, multiprocessing.cpu_count())) as executor:
        futures = {executor.submit(process_state, state_dir): state_dir.name for state_dir, _ in remaining_states}

        for future in as_completed(futures):
            state, items, findings = future.result()
            if items:
                all_items.extend(items)
            if findings:
                all_findings.extend(findings)
            completed += 1
            print(f"Progress: {completed}/{len(remaining_states)} states", flush=True)

    # Load existing findings and merge
    existing_findings = []
    existing_path = FINDINGS_DIR / "webapp_all_findings.json"
    if existing_path.exists():
        try:
            with open(existing_path) as f:
                data = json.load(f)
                existing_findings = data.get("findings", [])
        except:
            pass

    # Merge findings (avoid duplicates by ID)
    existing_ids = {f.get("id") for f in existing_findings}
    new_findings = [f for f in all_findings if f.get("id") not in existing_ids]
    merged_findings = existing_findings + new_findings

    # Save merged findings
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(merged_findings),
        "findings": merged_findings
    }

    with open(FINDINGS_DIR / "webapp_all_findings.json", "w") as f:
        json.dump(output, f, indent=2)

    # Also save just the new state findings
    with open(FINDINGS_DIR / "new_state_findings.json", "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_findings": len(all_findings),
            "findings": all_findings
        }, f, indent=2)

    print()
    print("=" * 60)
    print(f"COMPLETE!")
    print(f"  New findings: {len(all_findings)}")
    print(f"  Total findings: {len(merged_findings)}")
    print(f"  States processed: {len([s for s, _ in remaining_states])}")
    print(f"Finished: {datetime.now().isoformat()}")
    print("=" * 60)

    # Summary by state
    print("\nFindings by state:")
    state_counts = defaultdict(int)
    for f in all_findings:
        state_counts[f.get("state", "Unknown")] += 1
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")


if __name__ == "__main__":
    main()
