import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./decide9ja.db")
print(f"Connecting to: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

def check_schema():
    print("\n--- Schema Check ---")
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")
    
    if "rag_documents" in tables:
        print("\nTable 'rag_documents' exists.")
        columns = [c['name'] for c in inspector.get_columns("rag_documents")]
        print(f"Columns: {columns}")
        
        if "language" in columns:
            print("✅ 'language' column present.")
        else:
            print("❌ 'language' column MISSING.")
    
    if "documents" in tables:
        print("\nTable 'documents' exists (legacy table).")
    
    if "privacy_logs" in tables:
        print("\n✅ Table 'privacy_logs' exists.")
    else:
        print("\n❌ Table 'privacy_logs' MISSING.")

if __name__ == "__main__":
    check_schema()
