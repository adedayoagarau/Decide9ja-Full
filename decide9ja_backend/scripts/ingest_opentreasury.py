#!/usr/bin/env python3
"""
Ingest OpenTreasury 2025 Data
Reads daily payment CSV/Excel files from `processed_data/opentreasury/2025` and populates `transactions` table.
"""
import sqlite3
import pandas as pd
import glob
import os
import sys
from pathlib import Path
from datetime import datetime

# Configuration
BASE_DIR = Path("/Volumes/Crucial X10/Decide9ja")
RAW_DATA_DIR = BASE_DIR / "decide9ja_backend/raw_data/opentreasury/2025"
DB_PATH = BASE_DIR / "data/catalog.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_amount(text):
    try:
        return float(str(text).replace(',', '').replace('₦', '').strip())
    except:
        return 0.0

def ingest_daily_payments():
    print(f"Scanning {RAW_DATA_DIR}...")
    if not RAW_DATA_DIR.exists():
        print("Directory not found.")
        return

    # OpenTreasury files are usually excel or csv, located in Month subdirectories
    files = list(RAW_DATA_DIR.rglob("*.xlsx")) + list(RAW_DATA_DIR.rglob("*.csv"))
    print(f"Found {len(files)} files.")

    conn = get_db()
    cursor = conn.cursor()
    
    total_ingested = 0
    
    for file_path in files:
        try:
            print(f"Processing {file_path.name}...")
            if file_path.suffix == '.xlsx':
                # Read without header first to find the header row
                raw_df = pd.read_excel(file_path, header=None)
                
                # Find the row that contains 'NO' or 'PAYMENT NO'
                header_idx = -1
                for idx, row in raw_df.iterrows():
                    row_str = str(row.values).upper()
                    if 'NO' in row_str and 'AMOUNT' in row_str and 'BENEFICIARY' in row_str:
                        header_idx = idx
                        break
                
                if header_idx != -1:
                    df = pd.read_excel(file_path, header=header_idx)
                else:
                    # Fallback to default
                    df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
            
            # Normalize columns
            df.columns = [c.lower().strip() for c in df.columns]
            
            # Mapping based on typical OpenTreasury format
            # Expected: 'payment no', 'payer', 'beneficiary', 'amount', 'date', 'description'
            
            count = 0
            for _, row in df.iterrows():
                try:
                    payment_no = row.get('payment no', '') or row.get('payment_no', '') or row.get('no.', '')
                    if not payment_no: continue
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO transactions
                        (id, payment_date, payer, receiver, amount, description, source_url, state)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(payment_no),
                        row.get('date', datetime.now().strftime('%Y-%m-%d')),
                        row.get('payer', 'Federal Government'),
                        row.get('beneficiary', 'Unknown'),
                        parse_amount(row.get('amount', 0)),
                        row.get('description', 'No description'),
                        file_path.name,
                        'Federal'
                    ))
                    count += 1
                except Exception as sub_e:
                    continue
            
            print(f"  Ingested {count} rows.")
            total_ingested += count
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    conn.commit()
    conn.close()
    print(f"Total Processed: {total_ingested} transactions.")

if __name__ == "__main__":
    ingest_daily_payments()
