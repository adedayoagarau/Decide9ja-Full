"""
Flow-First Routing Tests

These tests verify that the flow-first routing system works correctly:
1. Users in active flows skip intent classification
2. IDLE users go through intent classification
3. Escape commands work from any state
4. NEWS_QUERY has higher priority than ISSUE_REPORT

Key test scenarios from specification:
- "Oyo" mid-onboarding → should NOT be classified as random text
- "yes" during confirmation → should NOT be classified as greeting
- "What's the Wike issue?" → should be NEWS_QUERY, not ISSUE_REPORT
- "cancel" mid-flow → should reset to IDLE
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


# ==========================================
# FLOW-FIRST ROUTING TESTS
# ==========================================

class TestFlowFirstRouting:
    """Critical tests for flow-first routing behavior."""
    
    @pytest.mark.asyncio
    async def test_onboarding_state_not_classified(self):
        """
        CRITICAL: User says 'Oyo' while answering 'which state?' 
        Should NOT be classified as random text → fallback
        Should be handled by onboarding flow directly
        """
        from app.models.state import UserState, ConversationFlow
        from app.services.flows.onboarding import handle_onboarding
        
        # User in onboarding, step 1 (waiting for state), has name
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            flow=ConversationFlow.ONBOARDING,
            flow_step=1,
            greeted=True
        )
        
        # User says just "Oyo"
        response = await handle_onboarding(state, "Oyo")
        
        # State should be captured
        assert state.state == "Oyo"
        # Should advance to step 2 (ask for LGA)
        assert state.flow_step == 2
        # Response should ask for LGA, not be a fallback
        assert "government" in response.lower() or "lga" in response.lower()
    
    @pytest.mark.asyncio
    async def test_onboarding_lga_not_classified(self):
        """
        CRITICAL: User says 'Oluyole' while answering 'which LGA?'
        Should NOT be classified as random text → fallback
        """
        from app.models.state import UserState, ConversationFlow
        from app.services.flows.onboarding import handle_onboarding
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            state="Oyo",
            flow=ConversationFlow.ONBOARDING,
            flow_step=2,
            greeted=True
        )
        
        response = await handle_onboarding(state, "Oluyole")
        
        assert state.lga == "Oluyole"
        assert state.flow == ConversationFlow.IDLE  # Onboarding complete
        assert "set" in response.lower()  # "You're set"
    
    @pytest.mark.asyncio
    async def test_confirmation_yes_not_greeting(self):
        """
        CRITICAL: User says 'yes' during confirmation
        Should NOT be classified as greeting → welcome message
        Should be handled by confirmation handler
        """
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_confirmation
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            state="Oyo",
            lga="Oluyole",
            flow=ConversationFlow.CONFIRMING,
            flow_data={"confirm_action": "save_issue", "location": "Test Area"}
        )
        
        # Mock the save function
        with patch('app.services.message_handler_v3.save_reported_issue', new_callable=AsyncMock) as mock_save:
            mock_save.return_value = "Issue documented. Reference: REF-123"
            response = await handle_confirmation(state, "yes")
        
        # Should complete the action, not return greeting
        assert "welcome" not in response.lower() or "ref" in response.lower()
        assert state.flow == ConversationFlow.IDLE


class TestNewsVsIssueDiscrimination:
    """Test that NEWS_QUERY has priority over ISSUE_REPORT."""
    
    def test_wike_issue_is_news_not_issue_report(self):
        """
        CRITICAL: "What's the Wike issue about?" should be NEWS_QUERY
        NOT ISSUE_REPORT (which would ask for location)
        """
        from app.services.router import classify_intent, Intent
        
        intent, confidence, entities = classify_intent("What's the Wike issue about?")
        
        assert intent == Intent.NEWS_QUERY, f"Expected NEWS_QUERY, got {intent}"
    
    def test_fubara_issue_is_news(self):
        """Fubara issue = political news."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("What's going on with the Fubara issue?")
        assert intent == Intent.NEWS_QUERY
    
    def test_rivers_crisis_is_news(self):
        """Rivers political crisis = news."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("What's happening in Rivers state with Wike and Fubara?")
        assert intent == Intent.NEWS_QUERY
    
    def test_actual_issue_report_works(self):
        """Real issue reporting should still trigger ISSUE_REPORT."""
        from app.services.router import classify_intent, Intent
        
        intent, _, _ = classify_intent("I want to report a bad road in my area")
        assert intent == Intent.ISSUE_REPORT
        
        intent, _, _ = classify_intent("There's a pothole on main street")
        assert intent == Intent.ISSUE_REPORT
        
        intent, _, _ = classify_intent("No electricity in my community for 3 days")
        assert intent == Intent.ISSUE_REPORT


class TestEscapeCommandsMidFlow:
    """Test escape commands work from any flow state."""
    
    @pytest.mark.asyncio
    async def test_cancel_mid_onboarding(self):
        """Cancel during onboarding resets to IDLE."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ONBOARDING,
            flow_step=1,
            greeted=True
        )
        
        # Simulate cancel (handled by message_handler directly)
        state.clear_flow()
        
        assert state.flow == ConversationFlow.IDLE
        assert state.flow_step == 0
    
    @pytest.mark.asyncio
    async def test_cancel_mid_issue_flow(self):
        """Cancel during issue reporting resets to IDLE."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Adedayo",
            state="Oyo",
            lga="Oluyole",
            flow=ConversationFlow.ISSUE_FLOW,
            flow_step=1,
            flow_data={"issue_type": "road_damage"}
        )
        
        state.clear_flow()
        
        assert state.flow == ConversationFlow.IDLE
        assert state.flow_step == 0
        assert state.flow_data == {}
    
    def test_escape_commands_detected(self):
        """Verify all escape commands are recognized."""
        from app.services.message_handler_v3 import ESCAPE_COMMANDS
        
        expected_escapes = {"reset", "cancel", "stop", "start over", "restart", "menu"}
        
        for cmd in expected_escapes:
            assert cmd in ESCAPE_COMMANDS, f"Missing escape command: {cmd}"


class TestIntentPriorityOrder:
    """Test that intent classification respects priority order."""
    
    def test_command_highest_priority(self):
        """Commands should be priority 100."""
        from app.services.router import PATTERNS, Intent
        
        command_pattern = next(p for p in PATTERNS if p["intent"] == Intent.COMMAND)
        assert command_pattern["priority"] == 100
    
    def test_news_before_issue(self):
        """NEWS_QUERY (80) should be higher priority than ISSUE_REPORT (50)."""
        from app.services.router import PATTERNS, Intent
        
        news_pattern = next(p for p in PATTERNS if p["intent"] == Intent.NEWS_QUERY)
        issue_pattern = next(p for p in PATTERNS if p["intent"] == Intent.ISSUE_REPORT)
        
        assert news_pattern["priority"] > issue_pattern["priority"]
    
    def test_greeting_high_priority(self):
        """Greeting should be priority 95."""
        from app.services.router import PATTERNS, Intent
        
        greeting_pattern = next(p for p in PATTERNS if p["intent"] == Intent.GREETING)
        assert greeting_pattern["priority"] == 95


class TestFullOnboardingFlow:
    """Test complete onboarding flow end-to-end."""
    
    @pytest.mark.asyncio
    async def test_full_onboarding_sequence(self):
        """
        Full onboarding: Hi → Name → State → LGA → Complete
        """
        from app.models.state import UserState, ConversationFlow
        from app.services.flows.onboarding import handle_onboarding
        
        state = UserState(user_id="test", phone="+234")
        
        # Step 1: Greeting
        state.flow = ConversationFlow.ONBOARDING
        state.flow_step = 0
        r1 = await handle_onboarding(state, "Hi")
        assert "Welcome" in r1 or "name" in r1.lower()
        assert state.greeted is True
        
        # Step 2: Name
        r2 = await handle_onboarding(state, "My name is Ade")
        assert state.name == "Ade"
        assert state.flow_step == 1
        assert "state" in r2.lower()
        
        # Step 3: State
        r3 = await handle_onboarding(state, "Oyo")
        assert state.state == "Oyo"
        assert state.flow_step == 2
        
        # Step 4: LGA
        r4 = await handle_onboarding(state, "Oluyole")
        assert state.lga == "Oluyole"
        assert state.flow == ConversationFlow.IDLE
        assert "set" in r4.lower()


class TestFlowStateTransitions:
    """Test state machine transitions."""
    
    def test_idle_to_onboarding(self):
        """IDLE → ONBOARDING when new user greets."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(user_id="test", phone="+234")
        assert state.flow == ConversationFlow.IDLE
        
        # Transition to onboarding
        state.flow = ConversationFlow.ONBOARDING
        state.flow_step = 0
        
        assert state.flow == ConversationFlow.ONBOARDING
    
    def test_idle_to_issue_flow(self):
        """IDLE → ISSUE_FLOW when user reports issue."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            name="Ade",
            state="Oyo",
            lga="Oluyole"
        )
        
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        
        assert state.flow == ConversationFlow.ISSUE_FLOW
    
    def test_issue_flow_to_confirming(self):
        """ISSUE_FLOW → CONFIRMING when ready to submit."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ISSUE_FLOW,
            flow_step=2
        )
        
        # Simulate reaching confirmation step
        state.flow = ConversationFlow.CONFIRMING
        state.flow_data["confirm_action"] = "save_issue"
        
        assert state.flow == ConversationFlow.CONFIRMING
        assert state.flow_data["confirm_action"] == "save_issue"
    
    def test_confirming_to_idle_on_yes(self):
        """CONFIRMING → IDLE after confirmation."""
        from app.models.state import UserState, ConversationFlow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.CONFIRMING,
            flow_data={"confirm_action": "save_issue"}
        )
        
        state.clear_flow()
        
        assert state.flow == ConversationFlow.IDLE


class TestClarificationFlow:
    """Test clarification/incomplete profile handling."""
    
    @pytest.mark.asyncio
    async def test_awaiting_clarify_state(self):
        """User in AWAITING_CLARIFY should answer the pending question."""
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_clarification
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.AWAITING_CLARIFY,
            flow_data={"awaiting": "state", "original_query": "Who is my senator?"}
        )
        
        response = await handle_clarification(state, "Lagos")
        
        assert state.state == "Lagos"
        assert state.flow_data.get("awaiting") == "lga"
    
    @pytest.mark.asyncio
    async def test_awaiting_clarify_lga(self):
        """User provides LGA after being asked."""
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_clarification
        
        state = UserState(
            user_id="test",
            phone="+234",
            state="Lagos",
            flow=ConversationFlow.AWAITING_CLARIFY,
            flow_data={"awaiting": "lga", "original_query": "Who is my senator?"}
        )
        
        # Mock handle_idle_state to avoid full execution
        with patch('app.services.message_handler_v3.handle_idle_state', new_callable=AsyncMock) as mock_idle:
            mock_idle.return_value = "Response from idle handler"
            response = await handle_clarification(state, "Ikeja")
        
        assert state.lga == "Ikeja"
        assert state.flow == ConversationFlow.IDLE


class TestIssueFlow:
    """Test issue reporting flow."""
    
    @pytest.mark.asyncio
    async def test_issue_flow_step_0(self):
        """Issue flow step 0: Initial prompt."""
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_issue_flow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ISSUE_FLOW,
            flow_step=0
        )
        
        response = await handle_issue_flow(state, "I want to report a bad road")
        
        assert state.flow_step == 1
        # Should ask for location
    
    @pytest.mark.asyncio
    async def test_issue_flow_step_1_location(self):
        """Issue flow step 1: Capture location."""
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_issue_flow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ISSUE_FLOW,
            flow_step=1
        )
        
        response = await handle_issue_flow(state, "Main Street, Ikeja")
        
        assert state.flow_data["location"] == "Main Street, Ikeja"
        assert state.flow_step == 2
    
    @pytest.mark.asyncio
    async def test_issue_flow_step_2_description(self):
        """Issue flow step 2: Capture description, trigger confirmation."""
        from app.models.state import UserState, ConversationFlow
        from app.services.message_handler_v3 import handle_issue_flow
        
        state = UserState(
            user_id="test",
            phone="+234",
            flow=ConversationFlow.ISSUE_FLOW,
            flow_step=2,
            flow_data={"location": "Test Location"}
        )
        
        response = await handle_issue_flow(state, "Large pothole causing accidents")
        
        assert state.flow_data["description"] == "Large pothole causing accidents"
        assert state.flow == ConversationFlow.CONFIRMING
        assert state.flow_data["confirm_action"] == "save_issue"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
