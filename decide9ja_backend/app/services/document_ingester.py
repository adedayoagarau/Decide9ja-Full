import os
import json
import logging
import uuid
import requests
from datetime import datetime
from pypdf import PdfReader
from app.database import SessionLocal, Document
from app.services.embeddings import get_embedding, embedding_to_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1500  # Characters
CHUNK_OVERLAP = 200

def ingest_pdf(file_path: str, title: str = None, category: str = "policy") -> str:
    """Read PDF, chunk text, and save to RAG."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    try:
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        doc_title = title or os.path.basename(file_path)
        return _process_text(full_text, doc_title, category, source=f"PDF Upload: {os.path.basename(file_path)}")
        
    except Exception as e:
        logger.error(f"PDF Ingestion failed: {e}")
        raise

def ingest_url(url: str, title: str = None, category: str = "policy") -> str:
    """Read URL content (simple text) and save to RAG."""
    try:
        # Simple text extraction (could be improved with BeautifulSoup)
        resp = requests.get(url)
        resp.raise_for_status()
        # Very basic HTML stripping or raw text usage
        # Ideally use readability or similar, but for now raw text if text/plain or basic
        text = resp.text
        
        # If HTML, we might want to strip tags (simple regex or just store raw if RAG handles it)
        # For robustness, let's assume the RAG model can handle some noise, or user provides clean URL
        # Better: use a simple regex to strip tags
        import re
        clean_text = re.sub('<[^<]+?>', '', text)
        
        doc_title = title or url
        return _process_text(clean_text, doc_title, category, source=f"URL: {url}")
        
    except Exception as e:
        logger.error(f"URL Ingestion failed: {e}")
        raise

def _process_text(text: str, title: str, category: str, source: str) -> str:
    """Chunk text, embed, and upsert."""
    db = SessionLocal()
    try:
        # 1. Chunking
        chunks = []
        for i in range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP):
            chunks.append(text[i:i + CHUNK_SIZE])
            
        # 2. Process chunks
        base_id = str(uuid.uuid4())[:8]
        count = 0
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"doc_{base_id}_{i}"
            
            # Embed
            embedding = get_embedding(chunk)
            
            # Metadata
            metadata = {
                "source_type": "dynamic_document",
                "category": category,
                "source": source,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "ingested_at": datetime.now().isoformat()
            }
            
            # Save
            doc = Document(
                doc_id=chunk_id,
                title=f"{title} (Part {i+1})",
                content=chunk,
                doc_type="dynamic_document",
                embedding_json=embedding_to_json(embedding),
                metadata_json=json.dumps(metadata),
                state="National" 
            )
            db.add(doc)
            count += 1
            
        db.commit()
        logger.info(f"Ingested '{title}' into {count} document chunks.")
        return f"Successfully indexed {count} chunks for {title}"
        
    finally:
        db.close()

if __name__ == "__main__":
    # Test with a dummy file if needed, or just run module
    pass
