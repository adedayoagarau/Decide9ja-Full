"""
FallbackAgent
=============
Handles queries that other agents can't answer.
Provides graceful failures with helpful suggestions.

Cost: FREE (template responses)
"""

import logging
from typing import Dict

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class FallbackAgent(BaseAgent):
    name = "fallback"
    description = "Graceful handling of unknown queries"
    tier = AgentTier.OUTPUT
    cost_level = CostLevel.FREE
    handled_intents = [Intent.UNKNOWN]

    # Fallback responses with suggestions
    FALLBACK_RESPONSES: Dict[str, Dict] = {
        "default": {
            "text": (
                "I'm not sure I understand that. Here's what I can help you with:\n\n"
                "*Find Your Representatives*\n"
                "\"Who is my senator?\" or \"My governor\"\n\n"
                "*Track Promises*\n"
                "\"What did Tinubu promise?\" or \"Promise tracker\"\n\n"
                "*2027 Elections*\n"
                "\"Who is running for president?\" or \"Election dates\"\n\n"
                "*Report Issues*\n"
                "\"Report bad road\" or \"No water in my area\"\n\n"
                "What would you like to know?"
            ),
            "buttons": [
                {"text": "My Representatives", "callback": "intent:rep_lookup"},
                {"text": "2027 Elections", "callback": "intent:election_info"},
                {"text": "Report Issue", "callback": "intent:report_issue"},
            ]
        },
        "not_in_database": {
            "text": (
                "I don't have that information in my database yet.\n\n"
                "Would you like me to search for recent news on this topic?"
            ),
            "buttons": [
                {"text": "Yes, search news", "callback": "action:web_search"},
                {"text": "No, thanks", "callback": "action:cancel"},
            ]
        },
        "location_needed": {
            "text": (
                "I need your location to answer that.\n\n"
                "What state are you in?"
            ),
            "buttons": [
                {"text": "Lagos", "callback": "state:lagos"},
                {"text": "Kano", "callback": "state:kano"},
                {"text": "Rivers", "callback": "state:rivers"},
                {"text": "FCT (Abuja)", "callback": "state:fct"},
            ]
        },
        "politician_not_found": {
            "text": (
                "I couldn't find that politician in my database.\n\n"
                "Try:\n"
                "- Checking the spelling\n"
                "- Using their full name\n"
                "- Asking \"Who is the governor of [state]?\"\n\n"
                "Who would you like to know about?"
            ),
            "buttons": []
        },
        "service_error": {
            "text": (
                "Sorry, I'm having trouble processing that right now.\n\n"
                "Please try again in a moment, or ask a different question."
            ),
            "buttons": [
                {"text": "Try again", "callback": "action:retry"},
                {"text": "Help menu", "callback": "intent:help"},
            ]
        },
        "out_of_scope": {
            "text": (
                "I'm focused on Nigerian politics and can't help with that.\n\n"
                "I can help you with:\n"
                "- Finding your elected representatives\n"
                "- 2027 election information\n"
                "- Tracking political promises\n"
                "- Reporting community issues\n\n"
                "What would you like to know about Nigerian politics?"
            ),
            "buttons": []
        }
    }

    async def can_handle(self, input: AgentInput) -> bool:
        return True  # Fallback handles everything

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # Determine why we're in fallback
        reason = input.handoff_reason or "default"

        # Map common reasons to response types
        reason_map = {
            "not_in_database": "not_in_database",
            "need_location": "location_needed",
            "location_needed": "location_needed",
            "politician_not_found": "politician_not_found",
            "error": "service_error",
            "service_error": "service_error",
            "out_of_scope": "out_of_scope",
        }

        response_key = reason_map.get(reason, "default")
        fallback = self.FALLBACK_RESPONSES.get(response_key, self.FALLBACK_RESPONSES["default"])

        return AgentOutput(
            success=True,
            response_text=fallback["text"],
            buttons=fallback.get("buttons", []),
            cost_level=CostLevel.FREE,
            analytics_tags={
                "fallback_reason": reason,
                "response_type": response_key,
                "original_query": input.raw_text[:100] if input.raw_text else ""
            }
        )
