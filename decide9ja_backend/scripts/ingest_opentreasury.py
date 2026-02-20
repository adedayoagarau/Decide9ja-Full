#!/usr/bin/env python3
"""
Ingest OpenTreasury 2025 Data
Reads daily payment CSV/Excel files from `processed_data/opentreasury/2025` and populates `transactions` table.
"""
import pandas as pd
import glob
import os
import sys
from pathlib import Path
from datetime import datetime

# Configuration
BASE_DIR = Path("/Volumes/Crucial X10/Decide9ja")
RAW_DATA_DIR = BASE_DIR / "decide9ja_backend/raw_data/opentreasury/2025"

# Add backend to path
sys.path.append(str(BASE_DIR / "decide9ja_backend"))
from app.database import SessionLocal, Transaction
from sqlalchemy.dialects.postgresql import insert

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

    session = SessionLocal()
    
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
            
            mappings = []
            for _, row in df.iterrows():
                try:
                    payment_no = row.get('payment no', '') or row.get('payment_no', '') or row.get('no.', '')
                    if not payment_no: continue
                    
                    mappings.append({
                        "id": str(payment_no),
                        "payment_date": str(row.get('date', datetime.now().strftime('%Y-%m-%d'))),
                        "payer": str(row.get('payer', 'Federal Government')),
                        "receiver": str(row.get('beneficiary', 'Unknown')),
                        "amount": parse_amount(row.get('amount', 0)),
                        "description": str(row.get('description', 'No description')),
                        "source_url": str(file_path.name),
                        "state": 'Federal'
                    })
                except Exception as sub_e:
                    continue
            
            if mappings:
                try:
                    stmt = insert(Transaction).values(mappings).on_conflict_do_nothing(index_elements=['id'])
                    session.execute(stmt)
                    session.commit()
                    print(f"  Ingested {len(mappings)} rows.")
                    total_ingested += len(mappings)
                except Exception as e:
                    session.rollback()
                    print(f"Commit error for {file_path.name}: {e}")
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    session.close()
    print(f"Total Processed: {total_ingested} transactions.")

if __name__ == "__main__":
    ingest_daily_payments()
