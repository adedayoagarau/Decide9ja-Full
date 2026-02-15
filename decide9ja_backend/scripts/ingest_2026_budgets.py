#!/usr/bin/env python3
"""
Ingest 2026 Budget PDFs
Gap 8: Data Refresh
"""
import sqlite3
import os
import re
import sys
from pathlib import Path

# Try importing pdfplumber, install if missing
try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    os.system("pip3 install pdfplumber")
    import pdfplumber

# Configuration
BASE_DIR = Path("/Volumes/Crucial X10/Decide9ja")
PDF_DIR = BASE_DIR / "data/raw_pdfs/2026"
DB_PATH = BASE_DIR / "data/catalog.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_amount(text):
    if not text:
        return 0
    # Remove currency symbols and whitespace
    cleaned = re.sub(r'[₦N,\s]', '', str(text))
    # Handle suffixes if present (though usually budget tables are explicit numbers)
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
        val = float(cleaned)
        return val * multiplier
    except ValueError:
        return 0

def extract_pdf(pdf_path):
    """Extract budget items from a single PDF"""
    items = []
    # Filename format: "{state}_2026_budget.pdf"
    filename = pdf_path.name
    state = filename.split('_')[0].replace('-', ' ').title()
    year = 2026
    
    print(f"Processing {state} ({filename})...")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            current_mda = "General"
            
            # Process first 50 pages to be safe/fast, or all if feasible.
            # Budget documents can be huge. Let's try 100 pages.
            for i, page in enumerate(pdf.pages[:100]):
                text = page.extract_text() or ""
                
                # Simple heuristic for MDA header (all caps, starts line)
                # Adjust regex as needed based on specific documents
                mda_lines = [line for line in text.split('\n') if "MINISTRY" in line and line.isupper()]
                if mda_lines:
                    current_mda = mda_lines[0].strip()

                tables = page.extract_tables()
                for table in tables:
                    if not table: continue
                    
                    for row in table:
                        # Heuristic: Budget rows usually have a code, description, and amount
                        # We need at least description and amount
                        # Row structure varies wildly between states.
                        # Strategy: Find the largest number in the row (Amount) and the longest text (Project)
                        
                        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                        if not any(cleaned_row): continue
                        
                        # Find potential amounts
                        amounts = []
                        description = ""
                        project_candidate = ""
                        
                        for cell in cleaned_row:
                            # Is it an amount?
                            if re.search(r'\d', cell) and len(cell) < 20: 
                                # Check if mostly digits/commas/dots
                                if re.match(r'^[₦N]?\s*[\d,]+(\.\d{2})?$', cell.replace(' ', '')):
                                    val = parse_amount(cell)
                                    if val > 1000: # Ignore tiny numbers/codes posing as amounts
                                        amounts.append(val)
                                        continue
                            
                            # If not amount, maybe description?
                            if len(cell) > len(description):
                                description = cell
                                
                        if amounts and description:
                            # Assume the largest amount is the current year allocation (often columns are Prev Year, Current Year)
                            # Or take the last column?
                            # Let's verify column headers? Too hard for generic.
                            # Taking the largest value found in the row is a reasonable heuristic for "Total Allocation"
                            amount = max(amounts)
                            
                            if amount > 100_000: # Filter out noise
                                items.append({
                                    "year": year,
                                    "jurisdiction": state,
                                    "mda": current_mda,
                                    "project": description,
                                    "amount": amount,
                                    "source_file": filename,
                                    "page": i + 1
                                })

    except Exception as e:
        print(f"Error extracting {filename}: {e}")
        
    return items

def ingest_items(items):
    conn = get_db()
    cursor = conn.cursor()
    
    print(f"Ingesting {len(items)} items into DB...")
    count = 0
    for item in items:
        try:
            cursor.execute("""
                INSERT INTO budgets (year, jurisdiction, mda, project, amount, source_file, page)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item['year'],
                item['jurisdiction'],
                item['mda'],
                item['project'],
                item['amount'],
                item['source_file'],
                item['page']
            ))
            count += 1
        except Exception as e:
            print(f"Insert error: {e}")
            
    conn.commit()
    conn.close()
    print(f"Successfully inserted {count} records.")

def main():
    if not PDF_DIR.exists():
        print(f"Directory not found: {PDF_DIR}")
        return

    all_items = []
    pdfs = list(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {PDF_DIR}")
    
    for pdf in pdfs:
        items = extract_pdf(pdf)
        all_items.extend(items)
        
    if all_items:
        ingest_items(all_items)
    else:
        print("No items extracted.")

if __name__ == "__main__":
    main()
