import os
import sys
import logging
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("db_migration")

def migrate_data(sqlite_url, postgres_url):
    """
    Migrates data from SQLite to PostgreSQL.
    Assumes schemas are identical (run migrations on Postgres first!).
    """
    logger.info("🚀 Starting Database Migration: SQLite -> Postgres")
    
    # Connect to SQLite (Source)
    sqlite_engine = create_engine(sqlite_url)
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)
    
    # Connect to Postgres (Destination)
    pg_engine = create_engine(postgres_url)
    pg_meta = MetaData()
    pg_meta.reflect(bind=pg_engine)
    
    # Create sessions
    SessionSQLite = sessionmaker(bind=sqlite_engine)
    session_sqlite = SessionSQLite()
    
    SessionPG = sessionmaker(bind=pg_engine)
    session_pg = SessionPG()
    
    # List of tables to migrate (in dependency order)
    # Skip alembic_version as we should run migrations on target
    tables_to_migrate = [
        "rag_documents",
        "politicians",
        "news_articles",
        "fact_checks",
        "issues",
        "issue_events",
        "bills",
        # Add other tables as needed, ensuring FK constraints aren't violated
    ]
    
    try:
        for table_name in tables_to_migrate:
            if table_name not in sqlite_meta.tables or table_name not in pg_meta.tables:
                logger.warning(f"⚠️ Skipping {table_name} (not found in both DBs)")
                continue
                
            logger.info(f"📦 Migrating table: {table_name}")
            
            # Get source data
            src_table = sqlite_meta.tables[table_name]
            dst_table = pg_meta.tables[table_name]
            
            # Select all rows
            rows = session_sqlite.query(src_table).all()
            if not rows:
                logger.info(f"   No data to migrate for {table_name}")
                continue
                
            logger.info(f"   Found {len(rows)} rows")
            
            # Insert into destination
            # We use core insert to avoid ORM overhead and issues
            count = 0
            for row in rows:
                row_dict = dict(row._mapping)
                try:
                    # Clean up Boolean fields for Postgres (SQLite uses 0/1)
                    # SQLAlchemy usually handles this, but raw dict might need help
                    
                    stmt = dst_table.insert().values(**row_dict)
                    session_pg.execute(stmt)
                    count += 1
                except IntegrityError:
                    session_pg.rollback()
                    logger.warning(f"   Skipping duplicate row in {table_name}")
                except Exception as e:
                    session_pg.rollback()
                    logger.error(f"   Error inserting row: {e}")
            
            session_pg.commit()
            logger.info(f"   ✅ Migrated {count} rows")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        session_pg.rollback()
    finally:
        session_sqlite.close()
        session_pg.close()
        logger.info("✨ Migration completed.")

if __name__ == "__main__":
    # Default paths
    SQLITE_URL = "sqlite:///./decide9ja.db"
    POSTGRES_URL = os.getenv("DATABASE_URL")
    
    if not POSTGRES_URL:
        logger.error("❌ DATABASE_URL environment variable is missing!")
        print("Usage: DATABASE_URL=postgresql://user:pass@host/db python scripts/migrate_sqlite_to_postgres.py")
        sys.exit(1)
        
    if "sqlite" in POSTGRES_URL:
         logger.error("❌ Target DATABASE_URL must be PostgreSQL, not SQLite!")
         sys.exit(1)

    migrate_data(SQLITE_URL, POSTGRES_URL)
