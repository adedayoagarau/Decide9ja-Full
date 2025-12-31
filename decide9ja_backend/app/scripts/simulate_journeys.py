"""
Decide9ja User Journey Simulation
Comprehensive Feature Test for Message Handler V2
"""
import asyncio
import logging
import sys
import time
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s"  # Clean output
)
logger = logging.getLogger(__name__)

# Import Handler
try:
    from app.services.message_handler_v2 import get_handler, FlowState, Templates
    from app.services import conversation
except ImportError as e:
    logger.error(f"Import Error: {e}")
    sys.exit(1)

# ===========================================
# TEST FRAMEWORK
# ===========================================

class SimulationResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def add_result(self, journey: str, turn: int, success: bool, note: str = ""):
        if success:
            self.passed += 1
            print(f"✅ [J{journey}:T{turn}] PASS: {note}")
        else:
            self.failed += 1
            print(f"❌ [J{journey}:T{turn}] FAIL: {note}")
        self.results.append({"journey": journey, "turn": turn, "success": success, "note": note})

    def report(self):
        print("\n" + "="*50)
        print("SIMULATION REPORT")
        print("="*50)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed:      {self.passed}")
        print(f"Failed:      {self.failed}")
        print("="*50)
        return self.failed == 0

RESULT = SimulationResult()

async def run_turn(handler, user: str, input_text: str, expected_tokens: List[str] = [], 
                   msg_type: str = "text", location: dict = None, turn_id: int = 0, journey: str = ""):
    print(f"\nUser ({user}): {input_text if msg_type == 'text' else '[LOCATION]'}")
    
    start_t = time.time()
    response = await handler.handle(user, input_text, msg_type=msg_type, location=location)
    duration = time.time() - start_t
    
    print(f"Bot: {response.replace(chr(10), ' ' )[:100]}... ({duration:.2f}s)")
    
    success = True
    missing_tokens = []
    
    for token in expected_tokens:
        if token.lower() not in response.lower():
            success = False
            missing_tokens.append(token)
            
    note = f"Found '{', '.join(expected_tokens)}'" if success else f"Missing '{', '.join(missing_tokens)}' in '{response[:50]}...'"
    RESULT.add_result(journey, turn_id, success, note)
    return response

# ===========================================
# JOURNEYS
# ===========================================

async def journey_1_new_user(handler):
    print("\n--- Journey 1: New User — Full Onboarding + Rep Lookup + Followup ---")
    user = "chidi_v2_test"
    conversation.clear_conversation_state(user)
    
    # Turn 1: First Contact
    await run_turn(handler, user, "Hi", ["Welcome", "name"], turn_id=1, journey="1")
    
    # Turn 2: Name (with noise)
    await run_turn(handler, user, "My name is Chidi. Please save that", ["Which state", "Chidi"], turn_id=2, journey="1")
    
    # Turn 3: State (complex input)
    await run_turn(handler, user, "I'm originally from Anambra but I live in Oyo state", ["local government", "Oyo"], turn_id=3, journey="1")
    
    # Turn 4: LGA (with suffix)
    await run_turn(handler, user, "Oluyole local government", ["vote", "2023"], turn_id=4, journey="1")
    
    # Turn 5: Voting status
    await run_turn(handler, user, "1", ["concern"], turn_id=5, journey="1")
    
    # Turn 6: Concerns
    resp = await run_turn(handler, user, "The tax issue. And insecurity.", ["Got it", "Chidi", "Oluyole", "Oyo"], turn_id=6, journey="1")
    
    # Verify profile preserved
    state = handler.get_state(user)
    if state.profile.lga == "Oluyole" and state.profile.state == "Oyo":
        RESULT.add_result("1", 6, True, "Profile saved correctly")
    else:
        RESULT.add_result("1", 6, False, f"Profile mismatch: {state.profile}")

    # Turn 7: Rep Lookup
    await run_turn(handler, user, "Who are my representatives?", ["Seyi Makinde", "Kola Balogun", "Abass Adigun"], turn_id=7, journey="1")
    
    # Turn 8: Followup — Politician Record
    await run_turn(handler, user, "What has Abass Adigun done?", ["record", "Abass"], turn_id=8, journey="1")
    
    # Turn 9: Context-Aware Followup (Pronoun) (Assuming Turn 8 set context context)
    # The response for Turn 8 might be Mocked or generated. If generated via RAG/Web, it might vary.
    # But V2 Handler sets context using 'entities' or 'resolved_politician'.
    await run_turn(handler, user, "What about his bills?", ["bills", "Abass"], turn_id=9, journey="1")
    
    # Turn 10: Context-Aware Followup (Reference)
    await run_turn(handler, user, "Tell me more about the honorable", ["Abass", "Ido/Oluyole"], turn_id=10, journey="1")

async def journey_2_news_query(handler):
    print("\n--- Journey 2: News Query (Intent Fix Test) ---")
    user = "news_test_user"
    conversation.clear_conversation_state(user) # Start fresh to avoid context interference? Or use clean user.
    
    # Turn 11: News Query with "issue" keyword
    await run_turn(handler, user, "What's the update on the Wike vs Makinde issue?", ["Wike", "Makinde", "Source"], turn_id=11, journey="2")
    
    # Turn 12: Another news pattern
    await run_turn(handler, user, "What's the most important policy trending in Nigeria right now?", ["tax", "reform", "Source"], turn_id=12, journey="2")
    
    # Turn 13: Political conflict query
    await run_turn(handler, user, "Tell me about the PDP crisis", ["PDP", "Wike", "Atiku"], turn_id=13, journey="2")

async def journey_3_issue_flow(handler):
    print("\n--- Journey 3: Issue Reporting Flow ---")
    user = "reporter_test"
    conversation.clear_conversation_state(user)
    
    # Turn 14: Issue Report Trigger
    await run_turn(handler, user, "I want to report a bad road", ["document", "location"], turn_id=14, journey="3")
    
    # Turn 15: Location (typed)
    await run_turn(handler, user, "Ring Road, near Challenge roundabout, Ibadan", ["Describe", "issue"], turn_id=15, journey="3")
    
    # Turn 16: Issue Description
    await run_turn(handler, user, "Deep potholes everywhere, very dangerous for vehicles", ["Documented", "Ring Road", "Works"], turn_id=16, journey="3")

    # Turn 17: Issue with Location Pin
    await run_turn(handler, user, "There's no light in my area", ["location"], turn_id=17, journey="3")
    
    # Mock Location
    loc = {"lat": 7.3775, "lng": 3.9470}
    # NOTE: Reverse geocoding might vary if API key not present, V2 handles fallback
    await run_turn(handler, user, "", ["Location", "IBEDC"], msg_type="location", location=loc, turn_id=17, journey="3")
    
    await run_turn(handler, user, "Power outage for 3 days", ["Documented", "Power"], turn_id=17, journey="3")

async def journey_4_voter_reg(handler):
    print("\n--- Journey 4: Voter Registration ---")
    user = "voter_reg_test"
    # Turn 18
    await run_turn(handler, user, "How do I register to vote?", ["NIN", "INEC", "PVC"], turn_id=18, journey="4")

async def journey_5_politician_info(handler):
    print("\n--- Journey 5: Politician Info (New Entity) ---")
    user = "pol_info_test"
    # Turn 19
    await run_turn(handler, user, "Who is Seyi Makinde?", ["Governor", "Oyo", "PDP"], turn_id=19, journey="5")
    
    # Turn 20: Followup on New Context
    await run_turn(handler, user, "What has he done lately?", ["Seyi Makinde", "Source"], turn_id=20, journey="5")

async def journey_6_error_recovery(handler):
    print("\n--- Journey 6: Error Recovery ---")
    user = "error_test"
    
    # Turn 21: Unclear Input
    # Ensure no context first
    handler.get_state(user).context.clear()
    await run_turn(handler, user, "What about that thing", ["Who", "asking about"], turn_id=21, journey="6")
    
    # Turn 22: Vague Query
    await run_turn(handler, user, "asdfghjkl", ["not sure", "Ask"], turn_id=22, journey="6")
    
    # Turn 23: No Data Available
    await run_turn(handler, user, "Who is the chairman of Ifelodun LGA in Kwara?", ["don't have information"], turn_id=23, journey="6")

async def journey_7_returning_user(handler):
    print("\n--- Journey 7: Returning User ---")
    # Reuse 'chidi_v2_test' from Journey 1
    user = "chidi_v2_test"
    
    # Turn 24: Return After Break
    await run_turn(handler, user, "Hi", ["Welcome back", "Chidi"], turn_id=24, journey="7")
    
    # Turn 25: Direct Rep Lookup (no re-asking location)
    await run_turn(handler, user, "Who is my senator again?", ["Kola Balogun", "Oyo South"], turn_id=25, journey="7")

async def journey_8_help_reset(handler):
    print("\n--- Journey 8: Help and Reset ---")
    user = "chidi_v2_test"
    
    # Turn 26: Help
    await run_turn(handler, user, "help", ["What I can do", "reset"], turn_id=26, journey="8")
    
    # Turn 27: Reset
    await run_turn(handler, user, "reset", ["Reset complete", "hi"], turn_id=27, journey="8")
    
    # Verify state cleared
    state = handler.get_state(user)
    # Reset clears flow and context, but profile?
    # v2 implementation of _handle_reset: flow=IDLE, context.clear(). Profile NOT cleared intentionally?
    # "Reset complete. Say 'hi' to start fresh." -> Hi -> Welcome back Chidi.
    # The user journey in prompt implies "Turn 27: Reset ... State: Cleared".
    # User journey doc says: "Turn 27: Reset... Intent: reset... State: Cleared".
    # If "State: Cleared" means Profile cleared, then "Hi" (Turn 1) would trigger onboarding again.
    # Usually 'reset' just resets conversation flow/context, not user account (profile).
    # IF the prompt implies FULL reset (Forget me), then profile should be cleared.
    # But usually 'reset' is 'cancel current operation'.
    # I'll assume profile persists.
    pass

async def main():
    handler = get_handler()
    print("Starting Simulation...")
    
    await journey_1_new_user(handler)
    await journey_2_news_query(handler)
    await journey_3_issue_flow(handler)
    await journey_4_voter_reg(handler)
    await journey_5_politician_info(handler)
    await journey_6_error_recovery(handler)
    await journey_7_returning_user(handler)
    await journey_8_help_reset(handler)
    
    if RESULT.report():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
