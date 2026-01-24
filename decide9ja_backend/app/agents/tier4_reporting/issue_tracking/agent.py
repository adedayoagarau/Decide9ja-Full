"""
IssueTrackingAgent
==================
Handles issue status lookup, user's reported issues, and issue interactions.

NO LLM CALLS - pure database operations via civic_issues services.
Cost: FREE
"""

import re
import logging

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
class IssueTrackingAgent(BaseAgent):
    name = "issue_tracking"
    description = "Track reported issues and view issue status"
    tier = AgentTier.REPORTING
    cost_level = CostLevel.FREE  # No LLM, database only
    handled_intents = [
        Intent.TRACK_ISSUE,
        Intent.MY_ISSUES,
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        intent = input.intent
        text = input.raw_text.lower()
        user_hash = input.user.phone_hash

        try:
            # Import services
            from app.services.civic_issues import (
                issue_tracking_service,
                issue_aggregate_service
            )

            # Check for issue ID in message
            issue_id_match = re.search(r'#?(D9J-[A-Z0-9]+|ISS\d+)', input.raw_text.upper())
            if issue_id_match:
                return await self._handle_issue_lookup(issue_id_match.group(1), issue_tracking_service)

            # Route by intent/keywords
            if intent == Intent.TRACK_ISSUE or "track" in text or "status" in text:
                # Check if we have a tracking ID from session
                session_tracking_id = input.session_data.get("last_tracking_id") if input.session_data else None
                if session_tracking_id:
                    return await self._handle_issue_lookup(session_tracking_id, issue_tracking_service)

                # Ask for tracking ID
                return AgentOutput(
                    success=True,
                    response_text="""🔍 *Track Issue Status*

Please provide your issue tracking ID.

Example: D9J-ABC12345

You received this ID when you submitted your report.""",
                    cost_level=CostLevel.FREE
                )

            elif "trending" in text:
                state = input.user.state
                lga = input.user.lga
                return await self._handle_trending(state, lga, issue_aggregate_service)

            elif "local" in text or "nearby" in text or "my area" in text:
                state = input.user.state
                lga = input.user.lga
                return await self._handle_local(state, lga, issue_aggregate_service)

            elif "upvote" in text or "me too" in text:
                # Get issue ID from context
                issue_id = input.session_data.get("active_issue_id") if input.session_data else None
                if issue_id:
                    return await self._handle_upvote(issue_id, user_hash, issue_tracking_service)
                return AgentOutput(
                    success=True,
                    response_text="Which issue do you want to upvote? Reply with the issue ID (e.g., D9J-ABC12345)",
                    cost_level=CostLevel.FREE
                )

            else:
                # Default: show user's issues
                return await self._handle_user_issues(user_hash, issue_tracking_service)

        except Exception as e:
            logger.error(f"Issue tracking error: {e}")
            return AgentOutput(
                success=False,
                response_text="Sorry, I couldn't load issue data. Please try again.",
                error=str(e),
                cost_level=CostLevel.FREE
            )

    async def _handle_issue_lookup(self, issue_id: str, service) -> AgentOutput:
        """Look up a specific issue."""
        issue = service.get_issue(issue_id)

        if not issue:
            return AgentOutput(
                success=True,
                response_text=f"Issue *{issue_id}* not found. Please check the tracking ID and try again.",
                cost_level=CostLevel.FREE
            )

        response = service.format_issue_detail(issue)
        return AgentOutput(
            success=True,
            response_text=response,
            session_data={"active_issue_id": issue_id},
            buttons=[
                {"text": "👍 Me Too", "callback": f"issue_upvote:{issue_id}"},
                {"text": "📋 My Issues", "callback": "my_issues"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "issue_detail", "issue_id": issue_id}
        )

    async def _handle_user_issues(self, user_hash: str, service) -> AgentOutput:
        """Show user's reported issues."""
        issues = service.get_user_issues(user_hash)

        if not issues:
            return AgentOutput(
                success=True,
                response_text="""📋 *Your Issue Reports*

You haven't reported any issues yet.

To report an issue, say "I want to report a problem" or describe the issue directly (e.g., "bad road on Main Street").""",
                cost_level=CostLevel.FREE
            )

        response = service.format_user_issues(issues)
        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "user_issues", "count": len(issues)}
        )

    async def _handle_trending(self, state: str, lga: str, service) -> AgentOutput:
        """Show trending issues."""
        data = service.get_trending(state=state, lga=lga)
        response = service.format_trending(data)
        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "trending_issues"}
        )

    async def _handle_local(self, state: str, lga: str, service) -> AgentOutput:
        """Show local issues."""
        if not state:
            return AgentOutput(
                success=True,
                response_text="""📍 *Local Issues*

I don't know your location yet.

Say "change location" to set your state and LGA, then try again.""",
                cost_level=CostLevel.FREE
            )

        data = service.get_local_issues(state=state, lga=lga)
        response = service.format_local_issues(data)
        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "local_issues", "state": state}
        )

    async def _handle_upvote(self, issue_id: str, user_hash: str, service) -> AgentOutput:
        """Upvote an issue (Me Too)."""
        result = service.upvote_issue(issue_id, user_hash)

        if result.get("success"):
            return AgentOutput(
                success=True,
                response_text=f"""👍 *Upvoted!*

Issue: #{issue_id}
Total upvotes: {result['upvotes']}
Status: {result['status'].title()}

The more people report this issue, the more attention it gets!""",
                cost_level=CostLevel.FREE
            )
        else:
            return AgentOutput(
                success=True,
                response_text=f"Couldn't upvote: {result.get('error', 'Unknown error')}",
                cost_level=CostLevel.FREE
            )
