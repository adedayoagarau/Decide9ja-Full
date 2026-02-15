import sys
import os
import time
import asyncio
import logging
from typing import Dict, Any

# Setup python path
sys.path.append("/Volumes/Crucial X10/Decide9ja/decide9ja_backend")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.database import SessionLocal, Document
from app.services.rag_router import RAGRouter, Intent

QUESTIONS = [
    # 1. Budget (Fiscal Intent) - English
    "How much did Lagos budget for health in 2026?",
    
    # 2. Budget - Pidgin
    "Wetin be the education budget for Kano?",
    
    # 3. Election (Election Intent) - Hausa
    "Yaya zabe na 2023?",  # "How was the 2023 election?"
    
    # 4. Legislator (Legislator Intent) - Igbo
    "Kedu onye bu senator Abia North?", # "Who is the senator for Abia North?"
    
    # 5. General (General Intent) - Yoruba
    "Bawo ni tinubu se n se?", # "How is Tinubu doing?"
    
    # 6. Bill (Bill Intent)
    "What is the status of the Student Loan Bill?",
    
    # 7. Local Terms Mapping (e.g. 'owo' -> budget)
    "Elo ni owo ipinle Eko?", # "How much is Lagos money/budget?"
]

async def run_test():
    print("Initializing DB Session...")
    db = SessionLocal()
    
    # Verify counts first
    print("\n=== DATA COUNTS ===")
    rag_count = db.query(Document).count()
    print(f"RAG Documents: {rag_count}")
    
    if rag_count == 0:
        print("WARNING: No RAG documents found. Ingestion might have failed.")
    
    print("\nInitializing RAG Router...")
    router = RAGRouter(db)
    
    print("\n=== STARTING ROUTER TEST ===")
    
    for i, q in enumerate(QUESTIONS):
        print(f"\n{'='*50}")
        print(f"[{i+1}/{len(QUESTIONS)}] Q: {q}")
        start_q = time.time()
        
        try:
            # Route query
            # Returns: {"response": str, "sources": List, "intent": str, "context": str}
            result = await router.route(q, filters={}, chat_history=[])
            
            elapsed = time.time() - start_q
            
            response = result.get("response", "")
            intent = result.get("intent", "unknown")
            sources = result.get("sources", [])
            
            print(f"  -> Time: {elapsed:.2f}s")
            print(f"  -> Intent: {intent}")
            print(f"  -> Response Preview: {response[:100]}...")
            print(f"  -> Sources Found: {len(sources)}")
            
            if sources:
                print("  -> Top Sources:")
                for s in sources[:3]:
                    # Handle different source structures
                    title = s.get('title') or s.get('doc_id') or 'Untitled'
                    print(f"     - [{s.get('doc_type', 'unknown')}] {title}")
            else:
                print("  -> NO SOURCES (Direct answer or fallback)")
                
        except Exception as e:
            print(f"  -> ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\nTest Complete.")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
