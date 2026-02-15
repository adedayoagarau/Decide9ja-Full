import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

# Get DB URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./decide9ja.db")
print(f"🔌 Connecting to database...")

try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    print(f"❌ Failed to create engine: {e}")
    sys.exit(1)

def run_migration(sql_file):
    if not os.path.exists(sql_file):
        print(f"❌ Migration file not found: {sql_file}")
        sys.exit(1)
        
    print(f"📂 Reading migration: {sql_file}")
    with open(sql_file, 'r') as f:
        sql_content = f.read()

    print("🚀 Executing migration...")
    try:
        with engine.connect() as conn:
            with conn.begin(): # Start transaction
                # Naive split by semicolon - sufficient for simple schema changes
                # dealing with stored procs would require more robust parsing
                statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                
                for i, statement in enumerate(statements):
                    print(f"   Executing statement {i+1}/{len(statements)}...")
                    conn.execute(text(statement))
                    
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_migration.py <path_to_sql_file>")
        sys.exit(1)
        
    run_migration(sys.argv[1])
