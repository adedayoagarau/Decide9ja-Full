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
    
    # 1. Ensure user is onboarded
    db = SessionLocal()
    phone = "+1234567891"
    
    # Generate hash for the fake onboarded user
    phone_hash = _hash_phone(phone)
    
    user = db.query(User).filter(User.phone_hash == phone_hash).first()
    if not user:
        user = User(
            phone_hash=phone_hash, 
            state="Lagos", 
            lga="Ikeja", 
            name="Test User",
            first_name="Test",
            onboarding_completed=True
        )
        db.add(user)
    else:
        user.onboarding_completed = True
        user.name = "Test User"
        user.first_name = "Test"
        
    db.commit()
    db.close()
    
    print("\n\n--- Sending compound query as onboarded user... ---")
    query = "what is the latest news about Tinubu and what were some of the news about him in 1999?"
    try:
        response = await handle_message(phone=phone, text=query)
        print(f"Final Response Output: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
