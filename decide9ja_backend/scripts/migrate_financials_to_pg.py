import os
import sys
from pathlib import Path

# Add the project root to the python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.database import Base, engine, Budget, Transaction, Finding

def migrate():
    print("Creating newly added Budget, Transaction, and Finding tables in PostgreSQL...")
    # This safely creates tables that are defined in Base but don't exist yet
    Base.metadata.create_all(bind=engine, tables=[Budget.__table__, Transaction.__table__, Finding.__table__])
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
