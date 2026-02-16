"""
ResponseComposerAgent
=====================
Handles final response generation for simple intents and template-based interactions.
This agent is the destination for GREETING, HELP, THANKS, and GOODBYE intents.

Cost: FREE (Template-based)
"""

import logging
from typing import Dict, Any

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
class ResponseComposerAgent(BaseAgent):
    name = "response_composer"
    description = "Handles template responses for simple intents"
    tier = AgentTier.OUTPUT
    cost_level = CostLevel.FREE
    handled_intents = [
        Intent.GREETING,
        Intent.HELP,
        Intent.THANKS,
        Intent.GOODBYE
    ]

    # Standard Templates
    TEMPLATES = {
        "greeting_response": (
            "Hello! 👋 I'm Tade, your guide to Nigerian politics.\n\n"
            "I can help you:\n"
            "• Find your representatives 🏛️\n"
            "• Track 2027 election candidates 🗳️\n"
            "• Report community issues 🚧\n"
            "• Check political promises ✅\n\n"
            "What would you like to know?"
        ),
        "help_menu": (
            "*Decide9ja Menu* 🇳🇬\n\n"
            "Try asking:\n"
            "• \"Who is my senator?\"\n"
            "• \"Who is running for president in 2027?\"\n"
            "• \"What did Tinubu promise?\"\n"
            "• \"Report bad road in my area\"\n"
            "• \"Follow Tinubu\" (get updates)\n\n"
            "Or just ask any question about Nigerian politics!"
        ),
        "thanks_response": (
            "You're welcome! Let me know if you need anything else. 🇳🇬"
        ),
        "goodbye_response": (
            "Goodbye! 👋 Come back anytime you have questions about Nigeria."
        ),
        "default_response": (
            "I'm here to help with Nigerian politics and civic issues. "
            "Try asking \"Help\" to see what I can do."
        )
    }

    async def can_handle(self, input: AgentInput) -> bool:
        """Handle if intent is assigned to this agent."""
        # Check if intent is one we handle
        return True

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1
        
        # Determine template to use
        # 1. From direct input data (e.g. passed by Router)
        template_key = input.context.get("template") if input.context else None
        
        # 2. Map from intent if not specified
        if not template_key and input.intent:
            if input.intent == Intent.GREETING:
                template_key = "greeting_response"
            elif input.intent == Intent.HELP:
                template_key = "help_menu"
            elif input.intent == Intent.THANKS:
                template_key = "thanks_response"
            elif input.intent == Intent.GOODBYE:
                template_key = "goodbye_response"

        # 3. Get text
        response_text = self.TEMPLATES.get(template_key, self.TEMPLATES["default_response"])

        # Add personalized greeting if user is known
        if template_key == "greeting_response" and input.user.first_name:
            response_text = f"Hello {input.user.first_name}! 👋" + response_text[6:]

        return AgentOutput(
            success=True,
            response_text=response_text,
            cost_level=CostLevel.FREE,
            analytics_tags={
                "response_template": template_key or "default",
                "intent": input.intent
            }
        )
