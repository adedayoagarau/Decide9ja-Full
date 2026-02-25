import sys
from pathlib import Path
BASE_DIR_PATH = Path("/Volumes/Crucial X10/Decide9ja")
sys.path.append(str(BASE_DIR_PATH / "decide9ja_backend"))
from app.database import engine, Transaction, SessionLocal
from sqlalchemy.dialects.postgresql import insert

session = SessionLocal()
try:
    mappings = [{"id": "TEST1", "payment_date": "2025-01-01", "payer": "A", "receiver": "B", "amount": 100, "description": "test", "state": "Federal", "source_url": "test.csv"}]
    stmt = insert(Transaction).values(mappings).on_conflict_do_nothing(index_elements=['id'])
    session.execute(stmt)
    session.commit()
    print("Insert success")
except Exception as e:
    print("Error:", e)
