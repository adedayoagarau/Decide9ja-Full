#!/usr/bin/env python3
"""
Ingest Intelligence Data (Gap 7)
Reads structured JSONs from `naijadata` and populates `catalog.db`.
"""
import json
import glob
import os
import sys
from pathlib import Path

# Paths
BASE_DIR_PATH = Path("/Volumes/Crucial X10/Decide9ja")
NAIJA_DATA_DIR = str(BASE_DIR_PATH / "data/naijadata")

sys.path.append(str(BASE_DIR_PATH / "decide9ja_backend"))
from app.database import SessionLocal, Finding, Transaction
from sqlalchemy.dialects.postgresql import insert

FINDINGS_FILE = os.path.join(NAIJA_DATA_DIR, "findings/all_findings_enriched.json")
TRANSACTIONS_FILE = os.path.join(NAIJA_DATA_DIR, "data/opentreasury/private_contractor_transactions.json")
CONTEXT_DIR = os.path.join(NAIJA_DATA_DIR, "data/context")

def ingest_findings():
    print(f"Loading findings from {FINDINGS_FILE}...")
    try:
        with open(FINDINGS_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Findings file not found at {FINDINGS_FILE}")
        return

    findings = data.get('findings', [])
    print(f"Found {len(findings)} findings. Ingesting...")

    session = SessionLocal()
    mappings = []
    
    for item in findings:
        try:
            # Flatten enriched analysis
            enriched_analysis = json.dumps(item.get('llm', {}))
            mappings.append({
                "id": str(item.get('id')),
                "risk_score": 50 if item.get('severity') == 'HIGH' else 10,
                "title": str(item.get('type')),
                "description": str(item.get('desc')),
                "jurisdiction": 'Federal',
                "year": item.get('year'),
                "mda": str(item.get('mda')),
                "amount": float(item.get('amount') or 0.0),
                "project_name": str(item.get('desc')),
                "anomaly_type": str(item.get('type')),
                "enriched_analysis": enriched_analysis
            })
        except Exception as e:
            print(f"Error preparing finding {item.get('id')}: {e}")

    if mappings:
        try:
            stmt = insert(Finding).values(mappings).on_conflict_do_nothing(index_elements=['id'])
            session.execute(stmt)
            session.commit()
            print(f"Successfully ingested {len(mappings)} findings.")
        except Exception as e:
            session.rollback()
            print(f"Commit error: {e}")
            
    session.close()

def ingest_transactions():
    print(f"Loading transactions from {TRANSACTIONS_FILE}...")
    try:
        with open(TRANSACTIONS_FILE, 'r') as f:
            transactions = json.load(f)
    except FileNotFoundError:
        print(f"Error: Transactions file not found at {TRANSACTIONS_FILE}")
        return

    print(f"Found {len(transactions)} transactions. Ingesting...")

    session = SessionLocal()
    mappings = []
    
    for item in transactions:
        try:
            mappings.append({
                "id": str(item.get('payment_no')),
                "payment_date": str(item.get('date')),
                "payer": str(item.get('organization')),
                "receiver": str(item.get('beneficiary')),
                "amount": float(item.get('amount') or 0.0),
                "description": str(item.get('description')),
                "source_url": str(item.get('source_file')),
                "state": 'Federal' # OpenTreasury is largely Federal
            })
        except Exception as e:
            print(f"Error preparing transaction {item.get('payment_no')}: {e}")

    if mappings:
        try:
            stmt = insert(Transaction).values(mappings).on_conflict_do_nothing(index_elements=['id'])
            session.execute(stmt)
            session.commit()
            print(f"Successfully ingested {len(mappings)} transactions.")
        except Exception as e:
            session.rollback()
            print(f"Commit error: {e}")
            
    session.close()

def ingest_context():
    print(f"Scanning context directory: {CONTEXT_DIR}...")
    if not os.path.exists(CONTEXT_DIR):
        print("Context directory not found.")
        return

    json_files = glob.glob(os.path.join(CONTEXT_DIR, "*.json"))
    conn = get_db()
    cursor = conn.cursor()

    for file_path in json_files:
        filename = os.path.basename(file_path)
        key = filename.replace('.json', '')
        print(f"Ingesting context: {key}")
        
        with open(file_path, 'r') as f:
            content = f.read() # Store as raw JSON text
        
        cursor.execute("""
            INSERT OR REPLACE INTO context_registry (key, category, content_json)
            VALUES (?, ?, ?)
        """, (key, 'general', content))
    
    conn.commit()
    conn.close()
    print("Context ingestion complete.")

if __name__ == "__main__":
    ingest_findings()
    ingest_transactions()
    # ingest_context() # Disabled pending Postgres migration of context_registry
