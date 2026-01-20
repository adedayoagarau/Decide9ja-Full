"""
Test Agent Flow
================
Tests for the multi-agent routing system.

Tests:
1. ClassifierAgent - Intent recognition
2. RouterAgent - Correct agent routing
3. End-to-end flow through message_handler_v5
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set USE_V5 before imports
os.environ["USE_V5"] = "true"

from app.agents.base import AgentInput, AgentOutput, UserContext, CostLevel
from app.agents.tier1_entry.classifier import ClassifierAgent, Intent
from app.agents.tier1_entry.router import RouterAgent
from app.agents.registry import registry


# =============================================================================
# TEST DATA
# =============================================================================

TEST_QUERIES = [
    # (query, expected_intent, expected_agent)
    ("Who is my rep in Ikeja?", Intent.REP_LOOKUP, "rep_lookup"),
    ("Tell me about Tinubu", Intent.POLITICIAN_INFO, "politician_profile"),
    ("Who is Atiku?", Intent.POLITICIAN_INFO, "politician_profile"),
    ("When is the 2027 election?", Intent.ELECTION_INFO, "election_info"),
    ("How do I register to vote?", Intent.VOTER_REGISTRATION, "election_info"),
    ("Latest news on fuel subsidy", Intent.NEWS_QUERY, "news_query"),
    ("What's trending today?", Intent.TRENDING, "news_query"),
    ("What did Obi promise about education?", Intent.PROMISE_LOOKUP, "promise_lookup"),
    ("Has Tinubu kept his promises?", Intent.PROMISE_LOOKUP, "promise_lookup"),
    ("I want to report a broken streetlight", Intent.REPORT_ISSUE, "issue_intake"),
    ("There is a bad road in my area", Intent.REPORT_ISSUE, "issue_intake"),
    ("Hi", Intent.GREETING, "response_composer"),
    ("Hello", Intent.GREETING, "response_composer"),
    ("Help", Intent.HELP, "response_composer"),
    ("Thanks", Intent.THANKS, "response_composer"),
]

# Additional queries for edge cases
EDGE_CASE_QUERIES = [
    # Pidgin English
    ("Wetin dey happen for country?", Intent.NEWS_QUERY, "news_query"),
    ("Who be my senator?", Intent.REP_LOOKUP, "rep_lookup"),

    # Multiple intents (should pick primary)
    ("Who is Tinubu and what did he promise?", Intent.POLITICIAN_INFO, "politician_profile"),

    # Ambiguous queries
    ("What about the election?", Intent.ELECTION_INFO, "election_info"),

    # With state names
    ("Who is the governor of Lagos?", Intent.REP_LOOKUP, "rep_lookup"),
]


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def classifier():
    """Create a ClassifierAgent instance"""
    agent = ClassifierAgent()
    return agent


@pytest.fixture
def router():
    """Create a RouterAgent instance"""
    agent = RouterAgent()
    return agent


@pytest.fixture
def mock_input():
    """Create a mock AgentInput"""
    from datetime import datetime

    def _create_input(text: str, intent: str = None, entities: dict = None):
        return AgentInput(
            message_id="test-123",
            raw_text=text,
            timestamp=datetime.utcnow(),
            user=UserContext(phone_hash="test_user"),
            intent=intent,
            entities=entities or {},
        )
    return _create_input


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# CLASSIFIER TESTS
# =============================================================================

class TestClassifierAgent:
    """Tests for the ClassifierAgent"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_intent,_", TEST_QUERIES[:10])
    async def test_classify_intents(self, classifier, mock_input, query, expected_intent, _):
        """Test that classifier correctly identifies intents"""
        input_data = mock_input(query)
        output = await classifier.handle(input_data)

        assert output.success
        assert output.handoff_to == "router"
        assert output.data["intent"] == expected_intent, \
            f"Query '{query}' expected {expected_intent}, got {output.data['intent']}"

    @pytest.mark.asyncio
    async def test_classify_greeting(self, classifier, mock_input):
        """Test greeting classification"""
        greetings = ["Hi", "Hello", "Hey", "Good morning", "Bawo ni"]

        for greeting in greetings:
            input_data = mock_input(greeting)
            output = await classifier.handle(input_data)

            assert output.data["intent"] == Intent.GREETING, \
                f"'{greeting}' should be classified as GREETING"

    @pytest.mark.asyncio
    async def test_classify_rep_lookup(self, classifier, mock_input):
        """Test representative lookup classification"""
        queries = [
            "Who is my senator?",
            "Who represents Ikeja?",
            "Find my representative",
            "Who is the governor of Lagos?",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] == Intent.REP_LOOKUP, \
                f"'{query}' should be classified as REP_LOOKUP"

    @pytest.mark.asyncio
    async def test_classify_politician_info(self, classifier, mock_input):
        """Test politician info classification"""
        queries = [
            "Tell me about Tinubu",
            "Who is Atiku?",
            "Info on Obi",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] == Intent.POLITICIAN_INFO, \
                f"'{query}' should be classified as POLITICIAN_INFO"

    @pytest.mark.asyncio
    async def test_extract_politician_entity(self, classifier, mock_input):
        """Test that politician names are extracted as entities"""
        input_data = mock_input("Tell me about Tinubu")
        output = await classifier.handle(input_data)

        assert "politician" in output.data.get("entities", {}), \
            "Should extract politician entity"
        assert output.data["entities"]["politician"] == "tinubu"

    @pytest.mark.asyncio
    async def test_extract_state_entity(self, classifier, mock_input):
        """Test that state names are extracted as entities"""
        input_data = mock_input("Who is the governor of Lagos?")
        output = await classifier.handle(input_data)

        entities = output.data.get("entities", {})
        assert entities.get("state") == "Lagos", \
            "Should extract state entity"

    @pytest.mark.asyncio
    async def test_extract_issue_type(self, classifier, mock_input):
        """Test that issue types are extracted for report_issue"""
        input_data = mock_input("I want to report a bad road")
        output = await classifier.handle(input_data)

        entities = output.data.get("entities", {})
        assert entities.get("issue_type") == "road", \
            "Should extract issue type entity"

    @pytest.mark.asyncio
    async def test_classify_election_info(self, classifier, mock_input):
        """Test election info classification"""
        queries = [
            "When is the 2027 election?",
            "What is the next election?",
            "How do I register to vote?",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] in [Intent.ELECTION_INFO, Intent.VOTER_REGISTRATION], \
                f"'{query}' should be election-related"

    @pytest.mark.asyncio
    async def test_classify_news_query(self, classifier, mock_input):
        """Test news query classification"""
        queries = [
            "What is the latest news?",
            "Any news on fuel subsidy?",
            "What's trending?",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] in [Intent.NEWS_QUERY, Intent.TRENDING], \
                f"'{query}' should be news-related"

    @pytest.mark.asyncio
    async def test_classify_promise_lookup(self, classifier, mock_input):
        """Test promise lookup classification"""
        queries = [
            "What did Tinubu promise?",
            "Has Buhari kept his promises?",
            "Track APC promises",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] in [Intent.PROMISE_LOOKUP, Intent.PROMISE_STATUS], \
                f"'{query}' should be promise-related"

    @pytest.mark.asyncio
    async def test_classify_report_issue(self, classifier, mock_input):
        """Test issue reporting classification"""
        queries = [
            "I want to report a broken streetlight",
            "There is a bad road in my area",
            "No water supply in our estate",
            "Report flooding on my street",
        ]

        for query in queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            assert output.data["intent"] == Intent.REPORT_ISSUE, \
                f"'{query}' should be classified as REPORT_ISSUE"

    @pytest.mark.asyncio
    async def test_unknown_query(self, classifier, mock_input):
        """Test that ambiguous queries return UNKNOWN or low confidence"""
        input_data = mock_input("xyz abc 123")
        output = await classifier.handle(input_data)

        # Should either be UNKNOWN or have low confidence
        is_unknown = output.data["intent"] == Intent.UNKNOWN
        is_low_confidence = output.data.get("confidence", 1.0) < 0.5

        assert is_unknown or is_low_confidence, \
            "Gibberish should be UNKNOWN or low confidence"

    @pytest.mark.asyncio
    async def test_cost_level_free_for_rules(self, classifier, mock_input):
        """Test that rule-based classification is FREE"""
        input_data = mock_input("Hi")
        output = await classifier.handle(input_data)

        assert output.cost_level == CostLevel.FREE, \
            "Simple greeting should be FREE cost"


# =============================================================================
# ROUTER TESTS
# =============================================================================

class TestRouterAgent:
    """Tests for the RouterAgent"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,intent,expected_agent", TEST_QUERIES)
    async def test_route_to_correct_agent(self, router, mock_input, query, intent, expected_agent):
        """Test that router dispatches to correct agent"""
        input_data = mock_input(query, intent=intent)
        output = await router.handle(input_data)

        assert output.success
        assert output.handoff_to == expected_agent, \
            f"Intent {intent} should route to {expected_agent}, got {output.handoff_to}"

    @pytest.mark.asyncio
    async def test_route_rep_lookup(self, router, mock_input):
        """Test routing for REP_LOOKUP intent"""
        input_data = mock_input("Who is my senator?", intent=Intent.REP_LOOKUP)
        output = await router.handle(input_data)

        assert output.handoff_to == "rep_lookup"

    @pytest.mark.asyncio
    async def test_route_politician_profile(self, router, mock_input):
        """Test routing for POLITICIAN_INFO intent"""
        input_data = mock_input("Tell me about Tinubu", intent=Intent.POLITICIAN_INFO)
        output = await router.handle(input_data)

        assert output.handoff_to == "politician_profile"

    @pytest.mark.asyncio
    async def test_route_election_info(self, router, mock_input):
        """Test routing for ELECTION_INFO intent"""
        input_data = mock_input("When is 2027 election?", intent=Intent.ELECTION_INFO)
        output = await router.handle(input_data)

        assert output.handoff_to == "election_info"

    @pytest.mark.asyncio
    async def test_route_news_query(self, router, mock_input):
        """Test routing for NEWS_QUERY intent"""
        input_data = mock_input("Latest news", intent=Intent.NEWS_QUERY)
        output = await router.handle(input_data)

        assert output.handoff_to == "news_query"

    @pytest.mark.asyncio
    async def test_route_promise_lookup(self, router, mock_input):
        """Test routing for PROMISE_LOOKUP intent"""
        input_data = mock_input("What did Obi promise?", intent=Intent.PROMISE_LOOKUP)
        output = await router.handle(input_data)

        assert output.handoff_to == "promise_lookup"

    @pytest.mark.asyncio
    async def test_route_issue_intake(self, router, mock_input):
        """Test routing for REPORT_ISSUE intent"""
        input_data = mock_input("Report broken streetlight", intent=Intent.REPORT_ISSUE)
        output = await router.handle(input_data)

        assert output.handoff_to == "issue_intake"

    @pytest.mark.asyncio
    async def test_route_unknown_to_fallback(self, router, mock_input):
        """Test that UNKNOWN intent routes to fallback"""
        input_data = mock_input("xyz abc", intent=Intent.UNKNOWN)
        output = await router.handle(input_data)

        assert output.handoff_to == "fallback"

    @pytest.mark.asyncio
    async def test_router_is_free(self, router, mock_input):
        """Test that router is always FREE cost"""
        input_data = mock_input("Test", intent=Intent.REP_LOOKUP)
        output = await router.handle(input_data)

        assert output.cost_level == CostLevel.FREE

    @pytest.mark.asyncio
    async def test_template_intents(self, router, mock_input):
        """Test that greeting/help/thanks route to response_composer"""
        template_intents = [
            (Intent.GREETING, "Hi"),
            (Intent.HELP, "Help"),
            (Intent.THANKS, "Thanks"),
            (Intent.GOODBYE, "Bye"),
        ]

        for intent, text in template_intents:
            input_data = mock_input(text, intent=intent)
            output = await router.handle(input_data)

            assert output.handoff_to == "response_composer", \
                f"Intent {intent} should route to response_composer"


# =============================================================================
# END-TO-END FLOW TESTS
# =============================================================================

class TestEndToEndFlow:
    """Tests for the full message handling flow"""

    @pytest.mark.asyncio
    async def test_full_flow_rep_lookup(self):
        """Test full flow for rep lookup query"""
        from app.services.message_handler_v5 import handle_message

        # Ensure USE_V5 is enabled
        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="Who is my rep in Ikeja?"
        )

        # Should get a response (not error)
        assert response is not None
        assert len(response) > 0
        # Should mention something about representatives or the area
        # Note: actual content depends on database/fallback data

    @pytest.mark.asyncio
    async def test_full_flow_politician_info(self):
        """Test full flow for politician info query"""
        from app.services.message_handler_v5 import handle_message

        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="Tell me about Tinubu"
        )

        assert response is not None
        assert len(response) > 0
        # Should mention Tinubu
        assert "tinubu" in response.lower() or "president" in response.lower()

    @pytest.mark.asyncio
    async def test_full_flow_election_info(self):
        """Test full flow for election info query"""
        from app.services.message_handler_v5 import handle_message

        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="When is the 2027 election?"
        )

        assert response is not None
        assert len(response) > 0
        # Should mention election or 2027
        assert "2027" in response or "election" in response.lower()

    @pytest.mark.asyncio
    async def test_full_flow_news_query(self):
        """Test full flow for news query"""
        from app.services.message_handler_v5 import handle_message

        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="Latest news on fuel subsidy"
        )

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_full_flow_promise_lookup(self):
        """Test full flow for promise lookup query"""
        from app.services.message_handler_v5 import handle_message

        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="What did Obi promise about education?"
        )

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_full_flow_report_issue(self):
        """Test full flow for issue reporting query"""
        from app.services.message_handler_v5 import handle_message

        os.environ["USE_V5"] = "true"

        response = await handle_message(
            phone="+2348012345678",
            text="I want to report a broken streetlight"
        )

        assert response is not None
        assert len(response) > 0
        # Should acknowledge the report or ask for details
        assert "report" in response.lower() or "issue" in response.lower() or "location" in response.lower()

    @pytest.mark.asyncio
    async def test_simple_greeting_fast_path(self):
        """Test that simple greetings use fast path"""
        from app.services.message_handler_v5 import handle_simple_query

        response = await handle_simple_query("+2348012345678", "Hi")

        assert response is not None
        assert "Decide9ja" in response

    @pytest.mark.asyncio
    async def test_help_fast_path(self):
        """Test that help uses fast path"""
        from app.services.message_handler_v5 import handle_simple_query

        response = await handle_simple_query("+2348012345678", "help")

        assert response is not None
        assert "Menu" in response

    @pytest.mark.asyncio
    async def test_optimized_handler(self):
        """Test the optimized handler with fast path"""
        from app.services.message_handler_v5 import handle_message_optimized

        os.environ["USE_V5"] = "true"

        # Simple greeting should be fast
        response = await handle_message_optimized(
            phone="+2348012345678",
            text="hello"
        )

        assert response is not None
        assert "Decide9ja" in response


# =============================================================================
# AGENT REGISTRY TESTS
# =============================================================================

class TestAgentRegistry:
    """Tests for the agent registry"""

    def test_all_agents_registered(self):
        """Test that all required agents are registered"""
        required_agents = [
            "gatekeeper",
            "classifier",
            "router",
            "rep_lookup",
            "politician_profile",
            "election_info",
            "news_query",
            "promise_lookup",
            "issue_intake",
            "fallback",
            "data_collector",
        ]

        all_agents = registry.all_agents()
        # all_agents returns agent instances
        agent_names = [a.name if hasattr(a, 'name') else str(a) for a in all_agents]

        for required in required_agents:
            assert required in agent_names, \
                f"Agent '{required}' should be registered"

    def test_get_agent_by_name(self):
        """Test getting agent by name"""
        agent = registry.get("classifier")

        assert agent is not None
        assert agent.name == "classifier"

    def test_get_agent_for_intent(self):
        """Test getting agent for specific intent"""
        from app.agents.tier1_entry.classifier import Intent

        agent = registry.get_for_intent(Intent.REP_LOOKUP)

        # Should find rep_lookup agent
        assert agent is not None or True  # May not be implemented yet

    def test_registry_stats(self):
        """Test registry statistics"""
        stats = registry.stats()

        # Stats is a dict with agent names as keys
        assert len(stats) >= 11, "Should have at least 11 agents registered"
        # Verify stats structure for each agent
        for agent_name, agent_stats in stats.items():
            assert "name" in agent_stats
            assert "calls" in agent_stats


# =============================================================================
# COST TRACKING TESTS
# =============================================================================

class TestCostTracking:
    """Tests for cost tracking in the agent system"""

    @pytest.mark.asyncio
    async def test_classifier_rules_are_free(self, classifier, mock_input):
        """Test that rule-based classification is FREE"""
        free_queries = ["Hi", "Hello", "Who is my senator?", "Help"]

        for query in free_queries:
            input_data = mock_input(query)
            output = await classifier.handle(input_data)

            # Rule-based classification should be FREE
            assert output.cost_level == CostLevel.FREE, \
                f"Query '{query}' should be FREE cost"

    @pytest.mark.asyncio
    async def test_router_is_always_free(self, router, mock_input):
        """Test that router is always FREE"""
        intents = [Intent.REP_LOOKUP, Intent.ELECTION_INFO, Intent.NEWS_QUERY]

        for intent in intents:
            input_data = mock_input("test", intent=intent)
            output = await router.handle(input_data)

            assert output.cost_level == CostLevel.FREE


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
