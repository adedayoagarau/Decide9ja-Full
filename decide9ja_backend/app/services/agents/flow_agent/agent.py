"""
Flow Agent Implementation

Handles multi-step conversation flows:
- ISSUE_REPORT / ISSUE_FLOW
- CONFIRMATION
- CLARIFICATION
- VOTER_REGISTRATION
"""
import logging
from typing import Set

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason
)
from app.services.agents.flow_agent.prompt import get_flow_prompt
from app.services.templates import get_template

logger = logging.getLogger(__name__)


class FlowAgent(BaseAgent):
    """
    Specialist agent for multi-step conversation flows.

    Handles issue reporting, confirmation, and clarification.
    """

    name = "flow"
    capabilities = [AgentCapability.FLOW_MANAGEMENT]
    handled_intents: Set[str] = {
        "issue_report",
        "voter_registration",
    }

    # Flow states this agent handles
    FLOW_STATES = {"issue_flow", "confirming", "awaiting_clarify"}

    def get_system_prompt(self) -> str:
        """Return the flow-focused system prompt."""
        return get_flow_prompt()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this is a flow-related intent or state."""
        if message.intent:
            if message.intent.lower() in self.handled_intents:
                return True
        # Check if user is in an active flow
        flow_state = message.metadata.get("flow_state", "").lower()
        return flow_state in self.FLOW_STATES

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Route to the appropriate flow handler."""
        intent = message.intent.lower() if message.intent else ""
        flow_state = message.metadata.get("flow_state", "").lower()

        try:
            # Check active flow state first
            if flow_state == "issue_flow":
                return await self._handle_issue_flow(message)

            elif flow_state == "confirming":
                return await self._handle_confirmation(message)

            elif flow_state == "awaiting_clarify":
                return await self._handle_clarification(message)

            # Handle initial intents
            if intent == "issue_report":
                return await self._start_issue_flow(message)

            elif intent == "voter_registration":
                return self._handle_voter_registration()

            else:
                return self.handoff("response", HandoffReason.INTENT_MISMATCH)

        except Exception as e:
            logger.exception(f"[FlowAgent] Error: {e}")
            return self.failure(f"Error in flow: {str(e)}")

    def _handle_voter_registration(self) -> AgentResult:
        """Handle voter registration info request."""
        response = get_template("voter_reg_info")
        return self.success(response)

    async def _start_issue_flow(self, message: AgentMessage) -> AgentResult:
        """Start the issue reporting flow."""
        response = get_template("issue_start")
        return self.success(response, data={
            "set_flow": "issue_flow",
            "set_flow_step": 0,
            "flow_data": {}
        })

    async def _handle_issue_flow(self, message: AgentMessage) -> AgentResult:
        """Handle issue reporting flow steps."""
        ctx = message.user_context
        step = ctx.flow_data.get("flow_step", 0)
        text = message.query

        if step == 0:
            # Initial prompt shown, waiting for category or location
            return self.success(
                get_template("issue_start"),
                data={"set_flow_step": 1}
            )

        elif step == 1:
            # Got location
            response = get_template("issue_got_location", location=text)
            return self.success(response, data={
                "set_flow_step": 2,
                "update_flow_data": {"location": text}
            })

        elif step == 2:
            # Got description - move to confirmation
            location = ctx.flow_data.get("location", "")

            response = get_template(
                "issue_confirm",
                issue_type="Community Issue",
                location=location,
                description=text
            )

            return self.success(response, data={
                "set_flow": "confirming",
                "update_flow_data": {
                    "description": text,
                    "confirm_action": "save_issue"
                }
            })

        return self.success(get_template("issue_start"))

    async def _handle_confirmation(self, message: AgentMessage) -> AgentResult:
        """Handle confirmation responses (yes/no)."""
        ctx = message.user_context
        text_lower = message.query.lower().strip()

        yes_words = {"yes", "y", "yeah", "yep", "sure", "ok", "confirm", "correct"}
        no_words = {"no", "n", "nope", "cancel", "wrong"}

        if text_lower in yes_words:
            action = ctx.flow_data.get("confirm_action")

            if action == "save_issue":
                return await self._save_issue(ctx)

            return self.success(
                "Confirmed. What else can I help with?",
                data={"clear_flow": True}
            )

        elif text_lower in no_words:
            return self.success(
                "No problem. What else can I help with?",
                data={"clear_flow": True}
            )

        else:
            return self.success(
                "Please respond with 'yes' to confirm or 'no' to cancel."
            )

    async def _save_issue(self, ctx) -> AgentResult:
        """Save a confirmed issue to the database."""
        try:
            from app.database import get_db, UserReport

            db = next(get_db())

            report = UserReport(
                user_hash=ctx.phone,  # Will be hashed by caller
                location=ctx.flow_data.get("location", ""),
                description=ctx.flow_data.get("description", ""),
                media_url=ctx.flow_data.get("media_url"),
                status="submitted"
            )
            db.add(report)
            db.commit()

            response = get_template(
                "issue_saved",
                issue_type="Community Issue",
                location=ctx.flow_data.get("location", "Unknown"),
                authority="relevant authorities",
                reference_id=f"ISS-{report.id:05d}"
            )

            return self.success(response, data={"clear_flow": True})

        except Exception as e:
            logger.error(f"Failed to save issue: {e}")
            return self.success(
                "I had trouble saving your report. Please try again later.",
                data={"clear_flow": True}
            )

    async def _handle_clarification(self, message: AgentMessage) -> AgentResult:
        """Handle clarification - re-process with new info."""
        # Clear the flow and hand off to router for re-classification
        return self.handoff("router", HandoffReason.COMPLETION, {
            "clear_flow": True,
            "reprocess_query": message.query
        })
