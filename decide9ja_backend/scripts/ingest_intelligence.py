#!/usr/bin/env python3
"""
Ingest Intelligence Data (Gap 7)
Reads structured JSONs from `naijadata` and populates `catalog.db`.
"""
import sqlite3
import json
import glob
import os
import sys

# Paths
BASE_DIR = "/Volumes/Crucial X10/Decide9ja/data"
NAIJA_DATA_DIR = "/Volumes/Crucial X10/Decide9ja/data/naijadata"
DB_PATH = os.path.join(BASE_DIR, "catalog.db")

FINDINGS_FILE = os.path.join(NAIJA_DATA_DIR, "findings/all_findings_enriched.json")
TRANSACTIONS_FILE = os.path.join(NAIJA_DATA_DIR, "data/opentreasury/private_contractor_transactions.json")
CONTEXT_DIR = os.path.join(NAIJA_DATA_DIR, "data/context")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

    conn = get_db()
    cursor = conn.cursor()
    
    count = 0
    for item in findings:
        try:
            # Flatten enriched analysis
            enriched_analysis = json.dumps(item.get('llm', {}))
            
            cursor.execute("""
                INSERT OR IGNORE INTO findings 
                (id, risk_score, title, description, jurisdiction, year, mda, amount, project_name, anomaly_type, enriched_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get('id'),
                50 if item.get('severity') == 'HIGH' else 10, # arbitrary score mapping for now
                item.get('type'), # using type as title
                item.get('llm', {}).get('analysis', item.get('desc')), # Use analysis as description if aval, else desc
                'Federal', # Default to Federal for now based on sample
                item.get('year'),
                item.get('mda'),
                item.get('amount'),
                item.get('desc'), # Project name from desc
                item.get('type'),
                enriched_analysis
            ))
            count += 1
            if count % 1000 == 0:
                print(f"Ingested {count} findings...")
        except Exception as e:
            print(f"Error ingesting finding {item.get('id')}: {e}")

    conn.commit()
    print(f"Successfully ingested {count} findings.")
    conn.close()

def ingest_transactions():
    print(f"Loading transactions from {TRANSACTIONS_FILE}...")
    try:
        with open(TRANSACTIONS_FILE, 'r') as f:
            transactions = json.load(f)
    except FileNotFoundError:
        print(f"Error: Transactions file not found at {TRANSACTIONS_FILE}")
        return

    print(f"Found {len(transactions)} transactions. Ingesting...")

    conn = get_db()
    cursor = conn.cursor()
    
    count = 0
    for item in transactions:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO transactions
                (id, payment_date, payer, receiver, amount, description, source_url, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get('payment_no'),
                item.get('date'),
                item.get('organization'),
                item.get('beneficiary'),
                item.get('amount'),
                item.get('description'),
                item.get('source_file'),
                'Federal' # OpenTreasury is largely Federal
            ))
            count += 1
            if count % 5000 == 0:
                print(f"Ingested {count} transactions...")
        except Exception as e:
            print(f"Error ingesting transaction {item.get('payment_no')}: {e}")

    conn.commit()
    print(f"Successfully ingested {count} transactions.")
    conn.close()

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
    ingest_context()
