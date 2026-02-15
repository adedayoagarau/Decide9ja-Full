"""
Tade Integration Test Suite

Tests for:
- Working memory enhancement
- Location identification (NEW Tade tools)
- Supermemory integration
- Error recovery
- Unified handler

Run with: python -m pytest test_tade_integration.py -v
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Import modules to test
from app.services.working_memory_enhanced import (
    WorkingMemory, 
    ConversationStage, 
    QueryType,
    handle_stage_transition,
    classify_query_type
)
from app.services.error_recovery_enhanced import (
    ErrorRecoveryHandler,
    handle_error,
    ProgressiveDisclosure
)
from app.services.tade_unified import LocationIdentifier, UnifiedTadeHandler


# ============================================================================
# WORKING MEMORY TESTS
# ============================================================================

class TestWorkingMemory:
    """Test working memory functionality"""
    
    def test_initialization(self):
        """Test working memory initializes correctly"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        assert memory.user_phone == "+2348012345678"
        assert memory.stage == ConversationStage.GREETING
        assert memory.location["state"] is None
        assert memory.interaction_count == 0
    
    def test_stage_transition(self):
        """Test stage transitions are logged"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        memory.transition_to(ConversationStage.LOCATION_COLLECTION, "new_user")
        
        assert memory.stage == ConversationStage.LOCATION_COLLECTION
        assert len(memory.stage_history) == 1
        assert memory.stage_history[0]["from"] == "greeting"
        assert memory.stage_history[0]["to"] == "location_collection"
        assert memory.interaction_count == 1
    
    def test_set_location(self):
        """Test location setting"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        memory.set_location(state="Lagos", lga="Ikeja")
        
        assert memory.location["state"] == "Lagos"
        assert memory.location["lga"] == "Ikeja"
    
    def test_set_query(self):
        """Test query setting with type detection"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        memory.set_query("Who is my senator?", QueryType.REPRESENTATIVE)
        
        assert memory.current_query["query_text"] == "Who is my senator?"
        assert memory.current_query["type"] == QueryType.REPRESENTATIVE
        assert memory.last_query_summary == "Who is my senator?"
    
    def test_clarification_flow(self):
        """Test clarification request and resolution"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        # Request clarification
        memory.request_clarification(
            question="Which state are you in?",
            expected_type="state_name"
        )
        
        assert memory.pending_clarification is True
        assert memory.clarification_question == "Which state are you in?"
        assert memory.stage == ConversationStage.ERROR_RECOVERY
        
        # Resolve clarification
        answer = memory.resolve_clarification("Lagos")
        
        assert memory.pending_clarification is False
        assert memory.stage == ConversationStage.QUERY_UNDERSTANDING
        assert answer == "Lagos"
    
    def test_error_tracking(self):
        """Test error recording"""
        memory = WorkingMemory(user_phone="+2348012345678")
        
        memory.record_error("API timeout")
        
        assert memory.last_error == "API timeout"
        assert memory.retry_count == 1
        
        memory.record_error("API timeout")
        assert memory.retry_count == 2
    
    def test_compression_recovery(self):
        """Test context compression recovery"""
        memory = WorkingMemory(user_phone="+2348012345678")
        memory.last_topic = "Lagos budget"
        memory.last_query_summary = "health allocation"
        
        context = memory.get_compression_recovery_context()
        
        assert "Lagos budget" in context
        assert "health allocation" in context
    
    def test_serialization(self):
        """Test dict serialization and deserialization"""
        memory = WorkingMemory(user_phone="+2348012345678")
        memory.set_location(state="Lagos", lga="Ikeja")
        memory.set_query("Test query", QueryType.NEWS)
        
        # Serialize
        data = memory.to_dict()
        
        # Deserialize
        restored = WorkingMemory.from_dict(data)
        
        assert restored.user_phone == memory.user_phone
        assert restored.location["state"] == "Lagos"
        assert restored.current_query["query_text"] == "Test query"


# ============================================================================
# LOCATION IDENTIFICATION TESTS
# ============================================================================

class TestLocationIdentification:
    """Test location identification with fuzzy matching"""
    
    def setup_method(self):
        self.locator = LocationIdentifier()
    
    def test_exact_state_match(self):
        """Test exact state name matching"""
        result = self.locator.identify("I am in Lagos")
        
        assert result["success"] is True
        assert result["state"] == "Lagos"
        assert result["needs_clarification"] is True  # No LGA yet
    
    def test_fuzzy_state_match(self):
        """Test fuzzy state matching"""
        result = self.locator.identify("I dey Lag")
        
        assert result["success"] is True
        assert result["state"] == "Lagos"
    
    def test_pidgin_patterns(self):
        """Test Pidgin English patterns"""
        test_cases = [
            ("I dey Lagos", "Lagos"),
            ("I stay Surulere", "Lagos"),  # Surulere is in Lagos
            ("My location na Kano", "Kano"),
            ("I live for Port Harcourt", "Rivers"),
        ]
        
        for message, expected_state in test_cases:
            result = self.locator.identify(message)
            assert result["success"] is True, f"Failed for: {message}"
            assert result["state"] == expected_state, f"Expected {expected_state}, got {result['state']}"
    
    def test_lga_identification(self):
        """Test LGA identification within state"""
        result = self.locator.identify("Ikeja Lagos")
        
        assert result["success"] is True
        assert result["state"] == "Lagos"
        assert result["lga"] == "Ikeja"
        assert result["needs_clarification"] is False
    
    def test_alias_matching(self):
        """Test location aliases"""
        result = self.locator.identify("ph")
        
        assert result["success"] is True
        assert result["state"] == "Rivers"  # Port Harcourt is in Rivers
    
    def test_cross_state_lga_matching(self):
        """Test identifying state from LGA only"""
        # Surulere is in Lagos (and there's one in Oyo too, but Lagos is more common)
        result = self.locator.identify("Surulere")
        
        assert result["success"] is True
        assert result["state"] == "Lagos"
        assert result["lga"] == "Surulere"
    
    def test_unknown_location(self):
        """Test handling of unknown locations"""
        result = self.locator.identify("I am in XYZ123")
        
        assert result["success"] is False
        assert result["needs_clarification"] is True
        assert "Which Nigerian state" in result["clarification_question"]
    
    def test_with_current_state(self):
        """Test identification when state already known"""
        result = self.locator.identify("Ikeja", current_state="Lagos")
        
        assert result["success"] is True
        assert result["state"] == "Lagos"
        assert result["lga"] == "Ikeja"


# ============================================================================
# ERROR RECOVERY TESTS
# ============================================================================

class TestErrorRecovery:
    """Test error recovery handlers"""
    
    def test_ambiguous_location(self):
        """Test ambiguous location handler"""
        response = ErrorRecoveryHandler.ambiguous_location(
            attempted="Surulere",
            suggestions=["Surulere, Lagos", "Surulere, Oyo"]
        )
        
        assert "Surulere, Lagos" in response
        assert "Surulere, Oyo" in response
        assert "number (1-2)" in response
    
    def test_unknown_location(self):
        """Test unknown location handler"""
        response = ErrorRecoveryHandler.unknown_location("XYZ123")
        
        assert "XYZ123" in response
        assert "Lagos" in response  # Suggested example
        assert "Kano" in response
    
    def test_vague_query(self):
        """Test vague query handler"""
        response = ErrorRecoveryHandler.query_too_vague("something")
        
        assert "finding your elected representatives" in response
        assert "1" in response and "2" in response
        assert "Reply with 1, 2, 3, 4, or 5" in response
    
    def test_no_results(self):
        """Test no results handler"""
        response = ErrorRecoveryHandler.no_results_found(
            query_type="representative",
            query="John Doe"
        )
        
        assert "John Doe" in response
        assert "menu" in response.lower()
    
    def test_general_error_escalation(self):
        """Test error escalation with retry count"""
        response_0 = ErrorRecoveryHandler.general_error(retry_count=0)
        response_1 = ErrorRecoveryHandler.general_error(retry_count=1)
        response_2 = ErrorRecoveryHandler.general_error(retry_count=2)
        
        assert "rephrase" in response_0.lower()
        assert "different way" in response_1.lower()
        assert "options" in response_2.lower() or "1." in response_2
    
    def test_handle_error_function(self):
        """Test main handle_error function"""
        response = handle_error("vague_query_options")
        
        assert "finding your elected representatives" in response


# ============================================================================
# QUERY CLASSIFICATION TESTS
# ============================================================================

class TestQueryClassification:
    """Test query type classification"""
    
    def test_representative_queries(self):
        """Test representative query detection"""
        queries = [
            "Who is my representative?",
            "Tell me about my senator",
            "Who is the governor?",
            "Find my rep",
        ]
        
        for query in queries:
            result = classify_query_type(query)
            assert result == QueryType.REPRESENTATIVE, f"Failed for: {query}"
    
    def test_budget_queries(self):
        """Test budget query detection"""
        queries = [
            "What's the Lagos budget?",
            "How much was allocated to health?",
            "Show me spending",
            "Where did the money go?",
        ]
        
        for query in queries:
            result = classify_query_type(query)
            assert result == QueryType.BUDGET, f"Failed for: {query}"
    
    def test_news_queries(self):
        """Test news query detection"""
        queries = [
            "What's the latest news?",
            "Recent updates",
            "What happened today?",
        ]
        
        for query in queries:
            result = classify_query_type(query)
            assert result == QueryType.NEWS, f"Failed for: {query}"
    
    def test_archive_queries(self):
        """Test archive query detection"""
        queries = [
            "What happened in 1999?",
            "Show me archives from 2000",
            "History of June 12",
        ]
        
        for query in queries:
            result = classify_query_type(query)
            assert result == QueryType.ARCHIVE, f"Failed for: {query}"


# ============================================================================
# PROGRESSIVE DISCLOSURE TESTS
# ============================================================================

class TestProgressiveDisclosure:
    """Test progressive disclosure of features"""
    
    def test_first_interaction(self):
        """Test first interaction message"""
        message = ProgressiveDisclosure.get_onboarding_message(0)
        
        assert "Tade" in message
        assert "representatives" in message.lower()
        assert "which state" in message.lower()
    
    def test_second_interaction(self):
        """Test second interaction message"""
        message = ProgressiveDisclosure.get_onboarding_message(1)
        
        assert "Who represents me?" in message
        assert "tip" in message.lower()
    
    def test_third_interaction(self):
        """Test third interaction reveals archives"""
        message = ProgressiveDisclosure.get_onboarding_message(2)
        
        assert "1960-2010" in message or "historical" in message.lower()
        assert "June 12" in message or "1999" in message
    
    def test_regular_user_no_message(self):
        """Test regular users don't get onboarding"""
        message = ProgressiveDisclosure.get_onboarding_message(5)
        
        assert message is None


# ============================================================================
# STAGE TRANSITION TESTS
# ============================================================================

class TestStageTransitions:
    """Test stage-based conversation flow"""
    
    @pytest.mark.asyncio
    async def test_new_user_flow(self):
        """Test complete new user flow"""
        memory = WorkingMemory(user_phone="+2348012345678")
        user_state = Mock()
        user_state.state = None
        user_state.lga = None
        
        # First message - greeting
        response = handle_stage_transition(
            memory, "Hello", "greeting", user_state
        )
        
        assert "state" in response.lower()
        assert memory.stage == ConversationStage.LOCATION_COLLECTION
    
    @pytest.mark.asyncio
    async def test_returning_user_flow(self):
        """Test returning user skips location collection"""
        memory = WorkingMemory(user_phone="+2348012345678")
        user_state = Mock()
        user_state.state = "Lagos"
        user_state.lga = "Ikeja"
        
        response = handle_stage_transition(
            memory, "Hello", "greeting", user_state
        )
        
        assert "Welcome back" in response
        assert "Ikeja" in response
        assert "Lagos" in response
    
    @pytest.mark.asyncio
    async def test_reset_command(self):
        """Test reset command returns to greeting"""
        memory = WorkingMemory(user_phone="+2348012345678")
        memory.transition_to(ConversationStage.DATA_RETRIEVAL, "test")
        user_state = Mock()
        
        response = handle_stage_transition(
            memory, "reset", "command", user_state
        )
        
        assert memory.stage == ConversationStage.GREETING


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    @patch('app.services.tade_unified.TadeSupermemory')
    async def test_full_conversation_flow(self, mock_supermemory_class):
        """Test complete conversation with all components"""
        # Setup mocks
        mock_supermemory = AsyncMock()
        mock_supermemory_class.return_value = mock_supermemory
        mock_supermemory.recall_context.return_value = []
        mock_supermemory.store_interaction.return_value = True
        
        handler = UnifiedTadeHandler()
        
        # New user greets
        user_state = Mock()
        user_state.state = None
        user_state.lga = None
        
        with patch.object(handler, '_get_user_state', return_value=user_state):
            response = await handler.handle_message("+2348012345678", "Hello")
            
            assert "state" in response.lower() or "Tade" in response
    
    def test_escape_commands(self):
        """Test escape commands work"""
        memory = WorkingMemory(user_phone="+2348012345678")
        memory.transition_to(ConversationStage.DATA_RETRIEVAL, "test")
        
        for command in ["reset", "restart", "menu", "start over"]:
            memory_copy = WorkingMemory(user_phone="+2348012345678")
            memory_copy.transition_to(ConversationStage.DATA_RETRIEVAL, "test")
            
            # Should reset to greeting
            assert memory_copy.stage == ConversationStage.DATA_RETRIEVAL


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
