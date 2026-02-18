"""
OnboardingAgent
===============
Bridges the Gatekeeper's handoff to the existing onboarding flow.

When the Gatekeeper detects a new user (no name/profile), it hands off
to this agent. This agent wraps app/services/flows/onboarding.py and
manages the multi-turn onboarding conversation:

    Flow: Name → State → LGA → Complete → hand back to Classifier

Cost: CHEAP (uses small LLM for intent classification during onboarding)
"""

import logging
from typing import Optional, Dict, Any

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.models.state import UserState, ConversationFlow
from app.services.flows.onboarding import handle_onboarding

logger = logging.getLogger(__name__)

# In-memory state store for onboarding sessions
# Key: phone_hash, Value: UserState
# TODO: Replace with Redis or DB-backed store for production persistence
_onboarding_sessions: Dict[str, UserState] = {}


@register_agent
class OnboardingAgent(BaseAgent):
    name = "onboarding"
    description = "Multi-turn new user onboarding (Name → State → LGA)"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.CHEAP  # Uses small LLM for classification
    handled_intents = ["__all__"]

    async def can_handle(self, input: AgentInput) -> bool:
        """Can handle any message from a new/unregistered user."""
        return True

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        phone_hash = input.user.phone_hash if hasattr(input.user, 'phone_hash') else (
            input.user.get("phone_hash") if isinstance(input.user, dict) else str(input.user)
        )

        # Get effective text (transcribed voice or raw text)
        text = input.raw_text.strip()
        if input.context:
            text = input.context.get("effective_text", text) or text

        # 1. Get or create onboarding session state
        state = self._get_or_create_session(phone_hash)

        # 2. Run the existing onboarding flow logic
        try:
            response_text = await handle_onboarding(state, text)
        except Exception as e:
            logger.error(f"Onboarding flow error for {phone_hash[:8]}...: {e}")
            return AgentOutput(
                success=False,
                response_text="Welcome to Decide9ja! 🇳🇬 I'm Tade, your civic assistant. Let's get you set up — what's your first name?",
                error=str(e),
                cost_level=CostLevel.FREE
            )

        # 3. Save updated session state
        _onboarding_sessions[phone_hash] = state

        # 4. Check if onboarding is now complete
        if state.is_onboarding_complete() or state.flow == ConversationFlow.IDLE:
            # Save user profile to database
            await self._save_user_profile(phone_hash, state)

            # Clean up in-memory session
            _onboarding_sessions.pop(phone_hash, None)

            # Check if there's a pending query from during onboarding
            if state.pending_query:
                logger.info(f"Onboarding complete for {phone_hash[:8]}..., "
                          f"processing pending query: {state.pending_query[:50]}")
                return AgentOutput(
                    success=True,
                    response_text=response_text,
                    handoff_to="classifier",
                    handoff_reason="onboarding_complete_with_pending_query",
                    data={
                        "pending_query": state.pending_query,
                        "user": {
                            "phone_hash": phone_hash,
                            "name": state.name,
                            "first_name": state.first_name,
                            "last_name": state.last_name,
                            "state": state.state,
                            "lga": state.lga,
                            "is_new_user": False,
                            "language": "en",
                        }
                    },
                    cost_level=CostLevel.CHEAP
                )

            logger.info(f"Onboarding complete for {phone_hash[:8]}... — "
                       f"{state.first_name} {state.last_name}, {state.lga}, {state.state}")

            return AgentOutput(
                success=True,
                response_text=response_text,
                data={
                    "onboarding_complete": True,
                    "user": {
                        "phone_hash": phone_hash,
                        "name": state.name,
                        "first_name": state.first_name,
                        "last_name": state.last_name,
                        "state": state.state,
                        "lga": state.lga,
                    }
                },
                cost_level=CostLevel.CHEAP
            )

        # 5. Still in onboarding — return the response (no handoff needed)
        # The next message will come back through gatekeeper → onboarding naturally,
        # because the user still has no name/profile in the database.
        return AgentOutput(
            success=True,
            response_text=response_text,
            data={
                "onboarding_step": state.flow_step,
                "collected": {
                    "first_name": state.first_name,
                    "last_name": state.last_name,
                    "state": state.state,
                    "lga": state.lga,
                }
            },
            cost_level=CostLevel.CHEAP
        )

    def _get_or_create_session(self, phone_hash: str) -> UserState:
        """
        Retrieve existing onboarding session or create a new one.
        """
        if phone_hash in _onboarding_sessions:
            logger.debug(f"Resuming onboarding session for {phone_hash[:8]}... "
                        f"(step {_onboarding_sessions[phone_hash].flow_step})")
            return _onboarding_sessions[phone_hash]

        # Create fresh onboarding state
        state = UserState(user_id=phone_hash, phone="")
        state.flow = ConversationFlow.ONBOARDING
        state.flow_step = 0
        state.greeted = False

        logger.info(f"New onboarding session for {phone_hash[:8]}...")
        _onboarding_sessions[phone_hash] = state
        return state

    async def _save_user_profile(self, phone_hash: str, state: UserState):
        """
        Save completed onboarding profile to the database.
        """
        try:
            if self.db:
                # TODO: Implement actual DB save based on your schema
                # Example for SQLAlchemy:
                # await self.db.execute(
                #     insert(User).values(
                #         phone_hash=phone_hash,
                #         first_name=state.first_name,
                #         last_name=state.last_name,
                #         name=state.name,
                #         state=state.state,
                #         lga=state.lga,
                #     )
                # )
                pass

            logger.info(f"Saved profile: {state.first_name} {state.last_name}, "
                       f"{state.lga}, {state.state}")

        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")
            # Don't fail the onboarding — profile can be saved on next interaction