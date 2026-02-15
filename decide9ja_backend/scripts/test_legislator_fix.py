import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.rag_router import RAGRouter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rag_test_fix")

async def test_fix():
    print("🚀 Testing Legislator Intent Fix")
    print("="*80)
    
    db = SessionLocal()
    router = RAGRouter(db)
    
    q = "Did my senator deliver the constituency project in Borno South?"
    print(f"Query: {q}")
    
    try:
        result = await router.route(q, filters={}, chat_history=[])
        intent = result.get("intent", "unknown")
        context = result.get("context", "")
        response = result.get("response", "")
        
        print(f"✅ Route Success!")
        print(f"Intent: {intent}")
        print(f"Context Length: {len(context)}")
        print(f"Context Preview: {context[:200]}...")
        print("-" * 40)
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"❌ Route Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_fix())
