#!/usr/bin/env python3
"""
Ingest Catalog Script
---------------------
Migrates OCR'd documents from the legacy `documents` table (OCR result storage)
into the RAG-optimized `rag_documents` table (semantic search).
"""
import sys
import os
import json
import sqlite3
import argparse
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.database import Base, Document, get_db
from app.services.embeddings import get_embedding, get_embeddings, embedding_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
CATALOG_DB_PATH = "/Volumes/Crucial X10/Decide9ja/data/catalog.db"
BATCH_SIZE = 50

def get_ocr_documents(conn: sqlite3.Connection, limit: int = None, offset: int = 0) -> List[sqlite3.Row]:
    """Fetch documents from the OCR source table."""
    query = """
    SELECT id, title, content, published_date, source_type, topics, processing_status
    FROM documents
    WHERE (processing_status = 'ocr_processed' OR processing_status = 'completed')
      AND length(content) > 100
      AND source_type = 'newspaper'
    ORDER BY published_date DESC
    """
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    
    cursor = conn.execute(query)
    return cursor.fetchall()

def get_total_ocr_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("""
    SELECT count(*) 
    FROM documents 
    WHERE (processing_status = 'ocr_processed' OR processing_status = 'completed')
      AND length(content) > 100
      AND source_type = 'newspaper'
    """)
    return cursor.fetchone()[0]

def count_rag_documents(session) -> int:
    return session.query(Document).filter(Document.doc_type == 'newspaper_archive').count()

def ingest_batch(session, rows: List[sqlite3.Row]):
    """Process a batch of rows and insert into RAG table."""
    new_docs = []
    texts_to_embed = []
    doc_data_list = []
    
    for row in rows:
        doc_id = row['id']
        
        # Check if exists
        exists = session.query(Document).filter(Document.doc_id == doc_id).first()
        if exists:
            continue
            
        content = row['content']
        title = row['title'] or f"Newspaper Scan ({row['published_date']})"
        
        # Truncate content
        embedding_text = f"{title}\n\n{content[:6000]}"
        
        texts_to_embed.append(embedding_text)
        
        metadata = {
            "source_type": row['source_type'],
            "published_date": row['published_date'],
            "original_id": doc_id,
            "topics": row['topics']
        }
        
        doc_data_list.append({
            "doc_id": doc_id,
            "title": title,
            "content": content,
            "metadata_json": json.dumps(metadata)
        })
    
    if not texts_to_embed:
        return 0
        
    # Generate embeddings in batch
    try:
        embeddings = get_embeddings(texts_to_embed)
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return 0
        
    # Create Document objects
    for data, embedding in zip(doc_data_list, embeddings):
        new_doc = Document(
            doc_type="newspaper_archive",
            doc_id=data["doc_id"],
            title=data["title"],
            content=data["content"],
            metadata_json=data["metadata_json"],
            embedding_json=embedding_to_json(embedding),
            category="newspaper",
            created_at=datetime.now()
        )
        new_docs.append(new_doc)
        
    if new_docs:
        session.bulk_save_objects(new_docs)
        session.commit()
        return len(new_docs)
    return 0

def main():
    parser = argparse.ArgumentParser(description="Ingest OCR catalog into RAG")
    parser.add_argument("--limit", type=int, help="Limit number of documents to ingest")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually write to DB")
    args = parser.parse_args()

    if not os.path.exists(CATALOG_DB_PATH):
        logger.error(f"Catalog DB not found at {CATALOG_DB_PATH}")
        sys.exit(1)

    # 1. Connect to Source (Raw SQLite)
    ocr_conn = sqlite3.connect(CATALOG_DB_PATH)
    ocr_conn.row_factory = sqlite3.Row
    
    # 2. Connect to Target (SQLAlchemy)
    db_url = f"sqlite:///{CATALOG_DB_PATH}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create rag_documents table if needed
    Base.metadata.create_all(engine)
    
    total_ocr = get_total_ocr_count(ocr_conn)
    current_rag = count_rag_documents(session)
    
    logger.info(f"Total OCR Documents: {total_ocr}")
    logger.info(f"Current RAG Documents: {current_rag}")
    
    if args.dry_run:
        logger.info("Dry run complete. Exiting.")
        return

    # 3. Batch Process
    limit = args.limit or total_ocr
    processed = 0
    ingested = 0
    offset = 0 
    
    while processed < limit:
        batch_limit = min(BATCH_SIZE, limit - processed)
        rows = get_ocr_documents(ocr_conn, limit=batch_limit, offset=offset)
        
        if not rows:
            break
            
        count = ingest_batch(session, rows)
        ingested += count
        
        processed += len(rows)
        offset += len(rows)
        
        logger.info(f"Processed {processed}/{limit} | Ingested: {ingested}")
        
    logger.info(f"Ingestion Complete. Total Ingested: {ingested}")

if __name__ == "__main__":
    main()
