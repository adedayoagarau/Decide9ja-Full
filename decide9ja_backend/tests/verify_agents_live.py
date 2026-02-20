
import sys
import os
import asyncio
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal, Politician, User
from app.agents.tier2_core.rep_lookup.agent import RepLookupAgent
from app.agents.tier2_core.politician_profile.agent import PoliticianProfileAgent
from app.agents.base import AgentInput, UserContext
from app.agents.tier1_entry.classifier import Intent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_agents():
    print("--- Verifying Agent DB Connections ---")
    
    # Check DB
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        pol_count = db.query(Politician).count()
        print(f"Database Stats: {user_count} Users, {pol_count} Politicians")
    except Exception as e:
        print(f"DB Connection Failed: {e}")
        # Create tables if not exist (implicit check)
        return
    finally:
        db.close()

    # Mock User
    user = UserContext(
        phone_hash="test_user_hash",
        state="Lagos",
        lga="Ikeja"
    )

    # 1. Test RepLookupAgent
    print("\n--- Testing RepLookupAgent (Lagos/Ikeja) ---")
    rep_agent = RepLookupAgent()
    input_reps = AgentInput(
        message_id="test1",
        raw_text="Who are my reps?",
        intent=Intent.REP_LOOKUP,
        user=user,
        entities = {}, timestamp=datetime.now()
    )
    
    output_reps = await rep_agent.handle(input_reps)
    print(f"Success: {output_reps.success}")
    print(f"Response: {output_reps.response_text}")
    
    if output_reps.data.get("representatives"):
         print(f"Found {len(output_reps.data['representatives'])} representatives")
         for r in output_reps.data['representatives']:
             print(f" - {r.get('name')} ({r.get('office_type')})")
    else:
         print("No reps found in DB for Lagos/Ikeja")

    # 2. Test PoliticianProfileAgent (Tinubu)
    print("\n--- Testing PoliticianProfileAgent (Tinubu) ---")
    profile_agent = PoliticianProfileAgent()
    input_profile = AgentInput(
        message_id="test2",
        raw_text="Tell me about Tinubu",
        intent=Intent.POLITICIAN_INFO,
        user=user,
        entities={"politician": "Tinubu"}, timestamp=datetime.now()
    )
    
    output_profile = await profile_agent.handle(input_profile)
    print(f"Success: {output_profile.success}")
    if output_profile.success:
        print(f"Response Start: {output_profile.response_text[:100]}...")
        data = output_profile.data or {}
        print(f"Data Source: {data.get('source')}")
    
if __name__ == "__main__":
    asyncio.run(verify_agents())
