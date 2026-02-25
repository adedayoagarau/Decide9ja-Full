import sys
import os
import asyncio
import logging

sys.path.append(os.getcwd())

from app.services.message_handler_v5 import handle_message, _hash_phone
import app.config.feature_flags as flags
from app.database import SessionLocal, User

logging.basicConfig(level=logging.INFO)

async def run():
    flags.AUTO_FALLBACK_ON_ERROR = False
    
    print("\n\n--- Testing '2026 budget for Oyo' ---")
    query1 = "2026 budget for Oyo"
    try:
        response = await handle_message(phone="+1234567891", text=query1)
        print(f"Final Response Output: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()

    print("\n\n--- Testing 'Tell me something interesting about Tinubu published in 1999?' ---")
    query2 = "Tell me something interesting about Tinubu published in 1999?"
    try:
        response = await handle_message(phone="+1234567891", text=query2)
        print(f"Final Response Output: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
