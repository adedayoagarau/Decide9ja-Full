"""
Conversation Flow Tests

Tests for the conversation state machine and flow handling:
- New user greeting
- Repeated greetings
- Full onboarding flow
- Escape commands
- Flow state persistence
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


# === STATE MODEL TESTS ===

class TestUserState:
    """Test UserState model."""
    
    def test_userstate_defaults(self):
        """Test default values for new UserState."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(user_id="test123", phone="+234")
        
        assert state.user_id == "test123"
        assert state.phone == "+234"
        assert state.name is None
        assert state.state is None
        assert state.lga is None
        assert state.flow == ConversationFlow.IDLE
        assert state.flow_step == 0
        assert state.greeted is False
    
    def test_is_onboarding_complete(self):
        """Test onboarding completion check."""
        from app.models.state import UserState
        
        # Incomplete
        state = UserState(user_id="test", phone="+234")
        assert state.is_onboarding_complete() is False
        
        state.name = "Adedayo"
        assert state.is_onboarding_complete() is False
        
        state.state = "Ogun"
        assert state.is_onboarding_complete() is False
        
        # Complete
        state.lga = "Ijebu North"
        assert state.is_onboarding_complete() is True
    
    def test_redis_serialization(self):
        """Test state can be serialized and deserialized."""
        from app.models.state import UserState, ConversationFlow
        import json
        
        state = UserState(
            user_id="test123",
            phone="+234",
            name="Adedayo",
            state="Ogun",
            lga="Ijebu North",
            flow=ConversationFlow.ONBOARDING,
            flow_step=2,
            greeted=True
        )
        
        # Serialize
        redis_data = state.to_redis()
        assert isinstance(redis_data, str)
        
        # Deserialize
        restored = UserState.from_redis(redis_data, "+234")
        
        assert restored.user_id == "test123"
        assert restored.name == "Adedayo"
        assert restored.state == "Ogun"
        assert restored.lga == "Ijebu North"
        assert restored.flow == ConversationFlow.ONBOARDING
        assert restored.flow_step == 2
        assert restored.greeted is True
    
    def test_clear_flow(self):
        """Test flow clearing."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(user_id="test", phone="+234")
        state.flow = ConversationFlow.ONBOARDING
        state.flow_step = 2
        state.flow_data = {"temp": "data"}
        
        state.clear_flow()
        
        assert state.flow == ConversationFlow.IDLE
        assert state.flow_step == 0
        assert state.flow_data == {}
    
    def test_add_to_history(self):
        """Test conversation history management."""
        from app.models.state import UserState
        
        state = UserState(user_id="test", phone="+234")
        
        # Add messages
        for i in range(10):
            state.add_to_history("user", f"Message {i}")
        
        # Should only keep last 6
        assert len(state.history) == 6
        assert state.history[0]["content"] == "Message 4"
        assert state.history[-1]["content"] == "Message 9"


class TestConversationFlow:
    """Test ConversationFlow enum."""
    
    def test_flow_values(self):
        """Test all flow states exist."""
        from app.models.state import ConversationFlow
        
        assert ConversationFlow.IDLE.value == "idle"
        assert ConversationFlow.ONBOARDING.value == "onboarding"
        assert ConversationFlow.ISSUE_FLOW.value == "issue_flow"
        assert ConversationFlow.AWAITING_CLARIFY.value == "clarify"
        assert ConversationFlow.CONFIRMING.value == "confirming"


# === ONBOARDING FLOW TESTS ===

class TestOnboardingFlow:
    """Test onboarding flow handler."""
    
    def test_extract_name_simple(self):
        """Test simple name extraction."""
        from app.services.flows.onboarding import extract_name
        
        assert extract_name("Adedayo") == "Adedayo"
        assert extract_name("John") == "John"
        assert extract_name("Fatima") == "Fatima"
    
    def test_extract_name_with_prefix(self):
        """Test name extraction with common prefixes."""
        from app.services.flows.onboarding import extract_name
        
        assert extract_name("My name is Adedayo") == "Adedayo"
        assert extract_name("I'm John") == "John"
        assert extract_name("Call me Fatima") == "Fatima"
        assert extract_name("I am Chidi") == "Chidi"
    
    def test_extract_name_rejects_greetings(self):
        """Test that greetings are not extracted as names."""
        from app.services.flows.onboarding import extract_name
        
        assert extract_name("Hi") is None
        assert extract_name("Hello") is None
        assert extract_name("Hey") is None
        assert extract_name("Good morning") is None
    
    def test_extract_nigerian_state(self):
        """Test Nigerian state extraction."""
        from app.services.flows.onboarding import extract_nigerian_state
        
        assert extract_nigerian_state("Lagos") == "Lagos"
        assert extract_nigerian_state("I'm from Ogun state") == "Ogun"
        assert extract_nigerian_state("FCT") == "FCT"
        assert extract_nigerian_state("Abuja") == "FCT"
        assert extract_nigerian_state("Cross River") == "Cross River"
        assert extract_nigerian_state("I live in Rivers State") == "Rivers"
    
    def test_extract_nigerian_state_not_found(self):
        """Test when state is not recognized."""
        from app.services.flows.onboarding import extract_nigerian_state
        
        assert extract_nigerian_state("California") is None
        assert extract_nigerian_state("random text") is None
    
    def test_extract_lga(self):
        """Test LGA extraction."""
        from app.services.flows.onboarding import extract_lga
        
        assert extract_lga("Ikeja", "Lagos") == "Ikeja"
        assert extract_lga("Ijebu North LGA", "Ogun") == "Ijebu North"
        assert extract_lga("Surulere Local Government", "Lagos") == "Surulere"
    
    @pytest.mark.asyncio
    async def test_onboarding_step_0_greeting(self):
        """Test initial greeting in onboarding."""
        from app.services.flows.onboarding import handle_onboarding
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ONBOARDING,
            flow_step=0,
            greeted=False
        )
        
        response = await handle_onboarding(state, "Hi")
        
        assert "Welcome" in response or "Tade" in response
        assert state.greeted is True
    
    @pytest.mark.asyncio
    async def test_onboarding_captures_name(self):
        """Test name is captured during onboarding."""
        from app.services.flows.onboarding import handle_onboarding
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ONBOARDING,
            flow_step=0,
            greeted=True
        )
        
        response = await handle_onboarding(state, "Adedayo")
        
        assert state.name == "Adedayo"
        assert state.flow_step == 1
        assert "state" in response.lower()  # Should ask for state
    
    @pytest.mark.asyncio
    async def test_onboarding_captures_state(self):
        """Test state is captured during onboarding."""
        from app.services.flows.onboarding import handle_onboarding
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            flow=ConversationFlow.ONBOARDING,
            flow_step=1,
            greeted=True
        )
        
        response = await handle_onboarding(state, "Ogun")
        
        assert state.state == "Ogun"
        assert state.flow_step == 2
        # Should ask for LGA
    
    @pytest.mark.asyncio
    async def test_onboarding_completes(self):
        """Test onboarding completion."""
        from app.services.flows.onboarding import handle_onboarding
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            state="Ogun",
            flow=ConversationFlow.ONBOARDING,
            flow_step=2,
            greeted=True
        )
        
        response = await handle_onboarding(state, "Ijebu North")
        
        assert state.lga == "Ijebu North"
        assert state.flow == ConversationFlow.IDLE
        assert "set" in response.lower()  # "You're set"


# === ESCAPE COMMANDS TESTS ===

class TestEscapeCommands:
    """Test escape/command handling."""
    
    def test_is_greeting(self):
        """Test greeting detection."""
        from app.services.router import is_greeting
        
        assert is_greeting("Hi") is True
        assert is_greeting("hello") is True
        assert is_greeting("Hey") is True
        assert is_greeting("Good morning") is True
        assert is_greeting("Good afternoon") is True
        
        assert is_greeting("Who is my senator") is False
        assert is_greeting("Tinubu") is False
    
    def test_command_intent_classification(self):
        """Test command intent is detected."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("reset")
        assert intent == Intent.COMMAND
        
        intent, _, _ = classify_intent("RESET")
        assert intent == Intent.COMMAND
        
        intent, _, _ = classify_intent("cancel")
        assert intent == Intent.COMMAND
    
    def test_thanks_intent_classification(self):
        """Test thanks intent is detected."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("thanks")
        assert intent == Intent.THANKS
        
        intent, _, _ = classify_intent("thank you")
        assert intent == Intent.THANKS


# === STATE MANAGER TESTS ===

class TestStateManager:
    """Test state manager."""
    
    def test_hash_phone(self):
        """Test phone hashing is consistent."""
        from app.services.state_manager import StateManager
        
        manager = StateManager()
        
        # Same phone should produce same hash
        hash1 = manager._hash_phone("+2341234567890")
        hash2 = manager._hash_phone("+2341234567890")
        assert hash1 == hash2
        
        # Different phones should produce different hashes
        hash3 = manager._hash_phone("+2341234567891")
        assert hash1 != hash3
    
    def test_hash_phone_normalizes(self):
        """Test phone hashing normalizes format."""
        from app.services.state_manager import StateManager
        
        manager = StateManager()
        
        # Different formats should produce same hash
        hash1 = manager._hash_phone("+2341234567890")
        hash2 = manager._hash_phone("whatsapp:+2341234567890")
        hash3 = manager._hash_phone("2341234567890")
        
        assert hash1 == hash2
        assert hash2 == hash3


# === INTENT CLASSIFICATION TESTS ===

class TestIntentClassification:
    """Test intent classification."""
    
    def test_greeting_intent(self):
        """Test greeting detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("Hi")
        assert intent == Intent.GREETING
        
        intent, _, _ = classify_intent("Hello Tade")
        assert intent == Intent.GREETING
    
    def test_rep_lookup_intent(self):
        """Test representative lookup detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("Who is my senator?")
        assert intent == Intent.REP_LOOKUP
        
        intent, _, _ = classify_intent("Who are my representatives?")
        assert intent == Intent.REP_LOOKUP
        
        intent, _, _ = classify_intent("Who represents me?")
        assert intent == Intent.REP_LOOKUP
    
    def test_politician_info_intent(self):
        """Test politician info detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("Who is Tinubu?")
        assert intent == Intent.POLITICIAN_INFO
        
        intent, _, _ = classify_intent("Tell me about Peter Obi")
        assert intent == Intent.POLITICIAN_INFO
    
    def test_news_intent(self):
        """Test news query detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("What's the latest news on the budget?")
        assert intent == Intent.NEWS_QUERY
        
        intent, _, _ = classify_intent("Any updates on the tax bill?")
        assert intent == Intent.NEWS_QUERY
    
    def test_help_intent(self):
        """Test help intent detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("help")
        assert intent == Intent.HELP
        
        intent, _, _ = classify_intent("What can you do?")
        assert intent == Intent.HELP
    
    def test_voter_registration_intent(self):
        """Test voter registration detection."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("How do I register to vote?")
        assert intent == Intent.VOTER_REGISTRATION
        
        intent, _, _ = classify_intent("How do I get my PVC?")
        assert intent == Intent.VOTER_REGISTRATION


# === REPEATED GREETING TEST ===

class TestRepeatedGreeting:
    """Test that repeated greetings don't restart onboarding."""
    
    @pytest.mark.asyncio
    async def test_greeted_user_not_re_greeted(self):
        """User who was greeted should not get welcome again."""
        from app.models.state import UserState, ConversationFlow
        from app.services.flows.onboarding import handle_onboarding
        
        # User already greeted, waiting for name
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ONBOARDING,
            flow_step=0,
            greeted=True
        )
        
        # User sends another greeting instead of name
        response = await handle_onboarding(state, "Hello")
        
        # Should ask for name, not full welcome again
        assert "Welcome" not in response or "name" in response.lower()
    
    def test_completed_user_stays_idle(self):
        """Completed user greeting stays in IDLE."""
        from app.models.state import UserState, ConversationFlow
        from app.services.router import classify_intent, Intent
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            state="Ogun",
            lga="Ijebu North",
            flow=ConversationFlow.IDLE
        )
        
        intent, _, _ = classify_intent("Hi", state)
        
        # Should be greeting intent, handler decides response
        assert intent == Intent.GREETING
        # Flow should stay IDLE
        assert state.flow == ConversationFlow.IDLE
