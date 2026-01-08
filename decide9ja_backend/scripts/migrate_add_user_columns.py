"""
Database Migration: Add missing User columns

This migration adds columns that exist in state_manager.py but are missing
from the production database.

Run with: python scripts/migrate_add_user_columns.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

# Convert postgres:// to postgresql:// for SQLAlchemy 2.0
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# Columns to add to the users table
COLUMNS_TO_ADD = [
    ("first_name", "VARCHAR(50)"),
    ("last_name", "VARCHAR(50)"),
    ("origin_state", "VARCHAR(50)"),
    ("origin_lga", "VARCHAR(100)"),
    ("residence_state", "VARCHAR(50)"),
    ("residence_lga", "VARCHAR(100)"),
    ("registered_state", "VARCHAR(50)"),
    ("registered_lga", "VARCHAR(100)"),
    ("ward", "VARCHAR(100)"),
    ("senatorial_district", "VARCHAR(100)"),
    ("federal_constituency", "VARCHAR(100)"),
    ("state_constituency", "VARCHAR(100)"),
    ("age_range", "VARCHAR(20)"),
    ("gender", "VARCHAR(20)"),
    ("has_pvc", "BOOLEAN"),
    ("interests", "TEXT"),
    ("topics_asked", "TEXT"),
    ("profile_completeness", "INTEGER DEFAULT 0"),
    ("message_count", "INTEGER DEFAULT 0"),
]


def column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table AND column_name = :column
    """), {"table": table, "column": column})
    return result.fetchone() is not None


def run_migration():
    """Run the migration to add missing columns."""
    print("=" * 60)
    print("Decide9ja Database Migration")
    print("Adding missing User columns")
    print("=" * 60)

    with engine.connect() as conn:
        # Check if users table exists
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'users'
        """))
        if not result.fetchone():
            print("ERROR: 'users' table does not exist!")
            print("Please run the main database setup first.")
            return False

        print(f"\nFound 'users' table. Checking {len(COLUMNS_TO_ADD)} columns...\n")

        added = 0
        skipped = 0

        for column_name, column_type in COLUMNS_TO_ADD:
            if column_exists(conn, "users", column_name):
                print(f"  [SKIP] {column_name} - already exists")
                skipped += 1
            else:
                try:
                    conn.execute(text(f"""
                        ALTER TABLE users
                        ADD COLUMN {column_name} {column_type}
                    """))
                    conn.commit()
                    print(f"  [ADD]  {column_name} ({column_type})")
                    added += 1
                except Exception as e:
                    print(f"  [FAIL] {column_name} - {e}")

        print("\n" + "=" * 60)
        print(f"Migration complete: {added} added, {skipped} skipped")
        print("=" * 60)

        return True


if __name__ == "__main__":
    try:
        success = run_migration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
