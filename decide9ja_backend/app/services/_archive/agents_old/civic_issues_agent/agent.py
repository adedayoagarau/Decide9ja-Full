"""
Civic Issues Agent - Handles community issue queries.

This is a database agent (no LLM calls) that routes to the appropriate
civic issues service based on intent.
"""

import re
import logging
from typing import Set

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability
)
from app.services.civic_issues import (
    issue_tracking_service,
    issue_aggregate_service
)

logger = logging.getLogger(__name__)


class CivicIssuesAgent(BaseAgent):
    """
    Handles civic issue queries:
    - Issue status lookup
    - User's reported issues
    - Trending issues
    - Local issues

    This agent does NOT use LLM - it's purely database operations.
    Note: Issue REPORTING is handled by the flow system in message_handler.
    """

    name = "civic_issues"
    capabilities = [AgentCapability.COMMUNITY]
    handled_intents: Set[str] = {
        "issue_status", "my_reports", "my_issues",
        "trending_issues", "local_issues", "issues_nearby",
        "upvote_issue", "verify_issue"
    }

    # Override - no LLM needed
    model = None
    max_tokens = 0

    def get_system_prompt(self) -> str:
        """Not used - no LLM calls."""
        return ""

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this agent handles the intent."""
        intent = (message.intent or "").lower()

        # Direct intent match
        if intent in self.handled_intents:
            return True

        # Issue ID in message
        if re.search(r'#?ISS\d+', message.query.upper()):
            return True

        # Keyword detection
        query_lower = message.query.lower()
        keywords = ["my report", "my issue", "issue status", "trending issue", "local issue", "issues in"]
        return any(kw in query_lower for kw in keywords)

    async def handle(self, message: AgentMessage) -> AgentResult:
        """
        Handle issue queries by routing to appropriate service.
        """
        intent = (message.intent or "").lower()
        query = message.query
        query_lower = query.lower()
        user_hash = message.user_context.phone
        ctx = message.user_context

        try:
            # Check for issue ID in message
            issue_id_match = re.search(r'#?(ISS\d+)', query.upper())
            if issue_id_match:
                return await self._handle_issue_lookup(issue_id_match.group(1))

            # Route by intent/keywords
            if "trending" in query_lower or intent == "trending_issues":
                return await self._handle_trending(ctx.state, ctx.lga)

            elif "local" in query_lower or "nearby" in query_lower or "my area" in query_lower or intent == "local_issues":
                return await self._handle_local(ctx.state, ctx.lga)

            elif "upvote" in query_lower or intent == "upvote_issue":
                # Need issue ID from context
                issue_id = message.metadata.get("active_issue_id")
                if issue_id:
                    return await self._handle_upvote(issue_id, user_hash)
                return self.success("Which issue do you want to upvote? Reply with the issue number (e.g., #ISS00123)")

            elif "verify" in query_lower or intent == "verify_issue":
                issue_id = message.metadata.get("active_issue_id")
                if issue_id:
                    return await self._handle_upvote(issue_id, user_hash)  # Same as upvote for now
                return self.success("Which issue do you want to verify? Reply with the issue number (e.g., #ISS00123)")

            else:
                # Default: show user's reports
                return await self._handle_user_issues(user_hash)

        except Exception as e:
            logger.error(f"Civic issues agent error: {e}")
            return self.failure(f"Failed to load issue data: {e}")

    async def _handle_issue_lookup(self, issue_id: str) -> AgentResult:
        """Look up a specific issue."""
        issue = issue_tracking_service.get_issue(issue_id)
        response = issue_tracking_service.format_issue_detail(issue)
        return self.success(response, {"type": "issue_detail", "issue_id": issue_id, "active_issue_id": issue_id})

    async def _handle_user_issues(self, user_hash: str) -> AgentResult:
        """Show user's reported issues."""
        issues = issue_tracking_service.get_user_issues(user_hash)
        response = issue_tracking_service.format_user_issues(issues)
        return self.success(response, {"type": "user_issues", "count": len(issues)})

    async def _handle_trending(self, state: str = None, lga: str = None) -> AgentResult:
        """Show trending issues."""
        data = issue_aggregate_service.get_trending(state=state, lga=lga)
        response = issue_aggregate_service.format_trending(data)
        return self.success(response, {"type": "trending", "data": data})

    async def _handle_local(self, state: str = None, lga: str = None) -> AgentResult:
        """Show local issues."""
        if not state:
            return self.success(
                "📍 I don't know your location yet.\n\nSay 'change location' to set your state and LGA, then try again."
            )

        data = issue_aggregate_service.get_local_issues(state=state, lga=lga)
        response = issue_aggregate_service.format_local_issues(data)
        return self.success(response, {"type": "local_issues", "data": data})

    async def _handle_upvote(self, issue_id: str, user_hash: str) -> AgentResult:
        """Upvote an issue."""
        result = issue_tracking_service.upvote_issue(issue_id, user_hash)

        if result.get("success"):
            return self.success(
                f"👍 Upvoted #{issue_id}!\n\nTotal upvotes: {result['upvotes']}\nStatus: {result['status'].title()}"
            )
        else:
            return self.success(f"Couldn't upvote: {result.get('error', 'Unknown error')}")


# Export for agent registry
def get_agent():
    """Factory function for agent registry."""
    return CivicIssuesAgent()
