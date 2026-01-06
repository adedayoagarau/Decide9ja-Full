"""
Tests for WhatsApp Message Handler
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Mock database before importing handler
@pytest.fixture(autouse=True)
def mock_db():
    """Mock database for all tests."""
    with patch('app.database.get_db') as mock:
        mock_session = MagicMock()
        mock.return_value = mock_session
        yield mock_session


class TestCommandHandling:
    """Tests for WhatsApp command parsing."""

    def test_parse_menu_command(self):
        """Test parsing menu command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("menu")
        assert cmd == ("menu", [])

    def test_parse_help_command(self):
        """Test parsing help command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("help")
        assert cmd == ("help", [])

    def test_parse_factcheck_command(self):
        """Test parsing fact-check command with argument."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("factcheck fuel price increase")
        assert cmd[0] == "factcheck"
        assert "fuel price increase" in " ".join(cmd[1])

    def test_parse_politician_command(self):
        """Test parsing politician lookup command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("politician Tinubu")
        assert cmd[0] == "politician"
        assert "Tinubu" in cmd[1]

    def test_parse_compare_command(self):
        """Test parsing compare command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("compare Tinubu vs Obi")
        assert cmd[0] == "compare"

    def test_parse_issue_command(self):
        """Test parsing issue report command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("report bad road on Ikorodu road")
        assert cmd[0] == "report"

    def test_parse_state_command(self):
        """Test parsing state info command."""
        from app.services.whatsapp_commands import parse_command

        cmd = parse_command("state Lagos")
        assert cmd[0] == "state"
        assert "Lagos" in cmd[1]


class TestMenuResponse:
    """Tests for menu response generation."""

    @pytest.mark.asyncio
    async def test_main_menu_response(self):
        """Test main menu response generation."""
        from app.services.whatsapp_commands import get_menu_response

        response = await get_menu_response()

        # Should contain key menu items
        assert "menu" in response.lower() or "MENU" in response
        assert any(word in response.lower() for word in ["politician", "election", "fact", "compare"])

    @pytest.mark.asyncio
    async def test_help_response(self):
        """Test help response generation."""
        from app.services.whatsapp_commands import get_help_response

        response = await get_help_response()

        # Should contain instructions
        assert any(word in response.lower() for word in ["help", "how", "command", "use"])


class TestGreetingHandling:
    """Tests for greeting detection and response."""

    def test_detect_greeting(self):
        """Test detecting greeting messages."""
        from app.services.whatsapp_commands import is_greeting

        assert is_greeting("hello") is True
        assert is_greeting("Hi") is True
        assert is_greeting("Good morning") is True
        assert is_greeting("Hey there") is True

    def test_non_greeting(self):
        """Test that regular messages aren't greetings."""
        from app.services.whatsapp_commands import is_greeting

        assert is_greeting("Who is the president") is False
        assert is_greeting("Tell me about elections") is False
        assert is_greeting("What's the fuel price") is False


class TestNigerianContext:
    """Tests for Nigerian context understanding."""

    def test_nigerian_greetings(self):
        """Test Nigerian greeting recognition."""
        from app.services.whatsapp_commands import is_greeting

        # Pidgin greetings
        assert is_greeting("Wetin dey") is True
        assert is_greeting("How far") is True
        assert is_greeting("How you dey") is True

    def test_state_normalization(self):
        """Test state name normalization."""
        from app.services.whatsapp_commands import normalize_state

        assert normalize_state("lagos") == "Lagos"
        assert normalize_state("FCT") == "Federal Capital Territory"
        assert normalize_state("abuja") == "Federal Capital Territory"
        assert normalize_state("Rivers") == "Rivers"


class TestNumberedMenuSelection:
    """Tests for numbered menu selection."""

    def test_number_selection(self):
        """Test numbered menu option selection."""
        from app.services.whatsapp_commands import parse_numbered_selection

        # Single digit
        assert parse_numbered_selection("1") == 1
        assert parse_numbered_selection("5") == 5

        # With prefix
        assert parse_numbered_selection("#1") == 1
        assert parse_numbered_selection("Option 3") == 3

    def test_invalid_number_selection(self):
        """Test invalid numbered selections."""
        from app.services.whatsapp_commands import parse_numbered_selection

        assert parse_numbered_selection("hello") is None
        assert parse_numbered_selection("") is None


class TestMessageValidation:
    """Tests for message validation."""

    def test_message_too_short(self):
        """Test rejection of too-short messages."""
        from app.services.whatsapp_commands import validate_message

        result = validate_message("")
        assert result["valid"] is False

    def test_message_too_long(self):
        """Test handling of too-long messages."""
        from app.services.whatsapp_commands import validate_message

        long_msg = "a" * 2000
        result = validate_message(long_msg)
        # Should either truncate or reject
        assert result is not None

    def test_valid_message(self):
        """Test validation of normal message."""
        from app.services.whatsapp_commands import validate_message

        result = validate_message("Who is the governor of Lagos?")
        assert result["valid"] is True


class TestConversationState:
    """Tests for conversation state management."""

    def test_get_user_state(self):
        """Test getting user conversation state."""
        from app.services.whatsapp_commands import ConversationState

        state = ConversationState.get_state("user_123")

        # New user should have empty state
        assert state is not None
        assert state.get("current_flow") is None

    def test_set_user_state(self):
        """Test setting user conversation state."""
        from app.services.whatsapp_commands import ConversationState

        ConversationState.set_state("user_456", {
            "current_flow": "politician_lookup",
            "step": 1
        })

        state = ConversationState.get_state("user_456")
        assert state["current_flow"] == "politician_lookup"

    def test_clear_user_state(self):
        """Test clearing user conversation state."""
        from app.services.whatsapp_commands import ConversationState

        ConversationState.set_state("user_789", {"flow": "test"})
        ConversationState.clear_state("user_789")

        state = ConversationState.get_state("user_789")
        assert state.get("flow") is None


class TestErrorHandling:
    """Tests for error handling in message processing."""

    @pytest.mark.asyncio
    async def test_handles_empty_message(self):
        """Test handling of empty messages."""
        from app.services.whatsapp_commands import handle_message_safe

        response = await handle_message_safe("user_err", "")

        # Should return helpful message, not crash
        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_handles_special_characters(self):
        """Test handling of special characters."""
        from app.services.whatsapp_commands import handle_message_safe

        response = await handle_message_safe(
            "user_special",
            "<script>alert('xss')</script>"
        )

        # Should sanitize and respond safely
        assert response is not None
        assert "<script>" not in response


class TestResponseFormatting:
    """Tests for response message formatting."""

    def test_format_politician_response(self):
        """Test formatting politician information."""
        from app.services.whatsapp_commands import format_politician_response

        politician = {
            "name": "Bola Tinubu",
            "position": "President",
            "party": "APC",
            "state": "Lagos"
        }

        response = format_politician_response(politician)

        assert "Bola Tinubu" in response
        assert "President" in response
        assert "APC" in response

    def test_format_election_response(self):
        """Test formatting election information."""
        from app.services.whatsapp_commands import format_election_response

        election = {
            "name": "Presidential Election",
            "date": "February 25, 2027",
            "type": "Federal"
        }

        response = format_election_response(election)

        assert "Presidential" in response
        assert "2027" in response

    def test_format_factcheck_response(self):
        """Test formatting fact-check result."""
        from app.services.whatsapp_commands import format_factcheck_response

        factcheck = {
            "claim": "Fuel price will increase",
            "verdict": "FALSE",
            "explanation": "No official announcement has been made"
        }

        response = format_factcheck_response(factcheck)

        assert "FALSE" in response or "false" in response.lower()
        assert "explanation" in response.lower() or "No official" in response


class TestWhatsAppIntegration:
    """Integration tests for WhatsApp handling."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete conversation flow."""
        from app.services.whatsapp_commands import handle_message_safe

        user_id = "integration_user"

        # 1. User sends greeting
        response1 = await handle_message_safe(user_id, "Hello")
        assert response1 is not None

        # 2. User asks for menu
        response2 = await handle_message_safe(user_id, "menu")
        assert "menu" in response2.lower() or any(
            char.isdigit() for char in response2
        )

        # 3. User asks a question
        response3 = await handle_message_safe(
            user_id,
            "Who is the president of Nigeria?"
        )
        assert response3 is not None
        assert len(response3) > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
