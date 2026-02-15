import sqlite3
import os

DB_PATH = "/Volumes/Crucial X10/Decide9ja/data/catalog.db"

def check_counts():
    if not os.path.exists(DB_PATH):
        print(f"Error: DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = [
        ("rag_documents", "Newspaper Archive (RAG)"),
        ("documents", "OCR Source Documents"),
        ("budgets", "Budget Records"),
        ("politicians", "Politician Profiles"),
        ("findings", "Intelligence Findings"),
        ("transactions", "Intelligence Transactions"),
        ("context_registry", "Context Registry")
    ]
    
    print(f"{'Table':<20} | {'Description':<30} | {'Count':<10}")
    print("-" * 65)
    
    total_rag = 0
    
    for table, desc in tables:
        try:
            cursor.execute(f"SELECT count(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table:<20} | {desc:<30} | {count:<10,}")
            if table == "rag_documents":
                total_rag = count
        except sqlite3.OperationalError:
             print(f"{table:<20} | {desc:<30} | {'(Missing)':<10}")

    print("-" * 65)
    
    # Check embedding population in RAG
    try:
        cursor.execute("SELECT count(*) FROM rag_documents WHERE embedding_json IS NOT NULL")
        embedded = cursor.fetchone()[0]
        print(f"RAG Documents with Embeddings: {embedded:,} / {total_rag:,}")
    except:
        pass

    conn.close()

if __name__ == "__main__":
    check_counts()
