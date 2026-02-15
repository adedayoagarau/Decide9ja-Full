
import sys
import os
import logging
from langdetect import detect, DetectorFactory

# Set seed for deterministic results
DetectorFactory.seed = 0

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, Document, SessionLocal
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backfill_language():
    """
    Iterates through all documents and updates their language field 
    based on content analysis.
    """
    db = SessionLocal()
    try:
        # Get total count
        total = db.query(Document).count()
        logger.info(f"Checking {total} documents for language backfill...")
        
        # Process in batches
        batch_size = 100
        processed = 0
        updated = 0
        
        # Get all docs (for now, optimization: verify if we should filter by language='en' only)
        # Since default is 'en', we might want to check everything just in case
        documents = db.query(Document).all()
        
        for doc in documents:
            try:
                if not doc.content or len(doc.content.strip()) < 10:
                    continue
                
                # Detect language
                # langdetect supports: en, af, so, sw, etc. 
                # Hausa (ha), Yoruba (yo), Igbo (ig) might be detected as others or 'en' if mixed.
                # We need to be careful.
                
                # Simple detection
                detected = detect(doc.content)
                
                # Map standard codes to our simplified codes
                lang_map = {
                    'en': 'en',
                    'ha': 'hausa',
                    'yo': 'yoruba',
                    'ig': 'igbo',
                    # pidgin often detects as English or broken English
                }
                
                # Custom naive check for specific Nigerian languages if langdetect fails or returns en
                # This helps if standard library doesn't support them well
                text_lower = doc.content.lower()
                if "kedu" in text_lower or "biko" in text_lower or "nna" in text_lower:
                    final_lang = "igbo"
                elif "bawo" in text_lower or "kilo" in text_lower or "ni bo" in text_lower:
                    final_lang = "yoruba"
                elif "sannu" in text_lower or "yaya" in text_lower:
                    final_lang = "hausa"
                elif "wetin" in text_lower or "no wahala" in text_lower or "abeg" in text_lower:
                    final_lang = "pidgin"
                else:
                    final_lang = lang_map.get(detected, 'en')
                
                # Update if different
                if doc.language != final_lang:
                    doc.language = final_lang
                    updated += 1
                    
            except Exception as e:
                logger.warning(f"Failed to detect language for doc {doc.id}: {e}")
            
            processed += 1
            if processed % batch_size == 0:
                db.commit()
                logger.info(f"Processed {processed}/{total} documents...")
        
        db.commit()
        logger.info(f"🎉 Backfill complete! Updated {updated} documents.")
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill_language()
