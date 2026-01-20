"""
Election Agent Implementation

Handles all 2027 election-related intents:
- FOLLOW_CANDIDATE, UNFOLLOW_CANDIDATE, MY_CANDIDATES
- COMPARE_CANDIDATES, CANDIDATE_SEARCH
- POLL_LIST, POLL_VOTE, POLL_RESULTS
- TRENDING_TOPICS, ELECTION_INFO
"""
import re
import logging
from typing import Set

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason
)
from app.services.agents.election_agent.prompt import get_election_prompt_with_context

logger = logging.getLogger(__name__)


class ElectionAgent(BaseAgent):
    """
    Specialist agent for 2027 Nigerian elections.

    Handles candidate tracking, polls, and election information.
    Loads ONLY its own focused prompt (~100 lines).
    """

    name = "election"
    capabilities = [AgentCapability.ELECTION_2027]
    handled_intents: Set[str] = {
        "follow_candidate",
        "unfollow_candidate",
        "my_candidates",
        "compare_candidates",
        "candidate_search",
        "poll_list",
        "poll_vote",
        "poll_results",
        "trending_topics",
        "election_info",
    }

    def get_system_prompt(self) -> str:
        """Return the election-focused system prompt."""
        return get_election_prompt_with_context()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this is an election-related intent."""
        if message.intent:
            return message.intent.lower() in self.handled_intents
        return False

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Route to the appropriate election handler."""
        intent = message.intent.lower() if message.intent else ""
        ctx = message.user_context

        try:
            if intent == "follow_candidate":
                return await self._handle_follow(message)

            elif intent == "unfollow_candidate":
                return await self._handle_unfollow(message)

            elif intent == "my_candidates":
                return await self._handle_my_candidates(message)

            elif intent == "compare_candidates":
                return await self._handle_compare(message)

            elif intent == "candidate_search":
                return await self._handle_candidate_search(message)

            elif intent == "poll_list":
                return await self._handle_poll_list(message)

            elif intent == "poll_vote":
                return await self._handle_poll_vote(message)

            elif intent == "poll_results":
                return await self._handle_poll_results(message)

            elif intent == "trending_topics":
                return await self._handle_trending(message)

            elif intent == "election_info":
                return await self._handle_election_info(message)

            else:
                # Unknown intent - hand off to response agent
                return self.handoff("response", HandoffReason.INTENT_MISMATCH)

        except Exception as e:
            logger.exception(f"[ElectionAgent] Error handling {intent}: {e}")
            return self.failure(f"Error processing election query: {str(e)}")

    async def _handle_follow(self, message: AgentMessage) -> AgentResult:
        """Handle following a candidate."""
        from app.services.election_2027.candidate_tracker import follow

        candidate_name = message.entities.get(
            "candidate_name",
            message.query.replace("follow", "").strip()
        )

        response = follow(message.user_context.phone, candidate_name)
        return self.success(response)

    async def _handle_unfollow(self, message: AgentMessage) -> AgentResult:
        """Handle unfollowing a candidate."""
        from app.services.election_2027.candidate_tracker import (
            get_candidate_tracker,
            get_candidate
        )

        candidate_name = message.entities.get(
            "candidate_name",
            message.query.replace("unfollow", "").strip()
        )

        tracker = get_candidate_tracker()
        candidate = get_candidate(candidate_name)

        if candidate:
            success, response = tracker.unfollow_candidate(
                message.user_context.phone,
                candidate.id
            )
            return self.success(response)

        return self.success(f"I couldn't find a candidate matching '{candidate_name}'.")

    async def _handle_my_candidates(self, message: AgentMessage) -> AgentResult:
        """Handle listing followed candidates."""
        from app.services.election_2027.candidate_tracker import get_my_candidates

        response = get_my_candidates(message.user_context.phone)
        return self.success(response)

    async def _handle_compare(self, message: AgentMessage) -> AgentResult:
        """Handle comparing candidates."""
        from app.services.election_2027.candidate_tracker import compare

        candidates_list = message.entities.get("candidates", [])

        if not candidates_list:
            # Try to parse from text
            text_clean = re.sub(
                r"compare|and|vs|versus",
                " ",
                message.query,
                flags=re.IGNORECASE
            )
            candidates_list = [c.strip() for c in text_clean.split() if c.strip()]

        response = compare(candidates_list[:4])  # Max 4 candidates
        return self.success(response)

    async def _handle_candidate_search(self, message: AgentMessage) -> AgentResult:
        """Handle searching for candidates by position."""
        from app.services.election_2027.candidate_tracker import get_candidate_tracker

        position = message.entities.get("position", "president")
        tracker = get_candidate_tracker()

        if position == "president":
            candidates = tracker.get_presidential_candidates()
            text = "🗳️ *2027 Presidential Candidates*\n\n"
            for c in candidates:
                emoji = "🟢" if c.party == "APC" else "🔴" if c.party == "PDP" else "🟡"
                incumbent = " (Incumbent)" if c.is_incumbent else ""
                text += f"{emoji} {c.name} - {c.party}{incumbent}\n"
            text += "\nSay a name for more details, or 'follow [name]' to get updates."
            return self.success(text)
        else:
            state_name = message.entities.get("state", message.user_context.state)
            candidates = tracker.get_gubernatorial_candidates(state_name)
            if candidates:
                text = f"🗳️ *2027 {state_name} Gubernatorial Candidates*\n\n"
                for c in candidates:
                    text += f"• {c.name} ({c.party})\n"
                return self.success(text)
            return self.success(
                f"I don't have gubernatorial candidates for {state_name} yet. Check back soon!"
            )

    async def _handle_poll_list(self, message: AgentMessage) -> AgentResult:
        """Handle listing available polls."""
        from app.services.election_2027.polling_system import get_user_polls

        ctx = message.user_context
        polls = get_user_polls(user_state=ctx.state, user_lga=ctx.lga)

        if not polls:
            return self.success("No active polls right now. Check back soon! 📊")

        text = "📊 *Available Polls*\n\n"
        for i, poll in enumerate(polls[:5], 1):
            text += f"{i}. {poll.title}\n"
        text += "\nReply with the poll number to participate."

        # Store poll IDs in response data for flow continuation
        return self.success(text, data={
            "available_polls": [p.id for p in polls[:5]]
        })

    async def _handle_poll_vote(self, message: AgentMessage) -> AgentResult:
        """Handle voting in a poll."""
        from app.services.election_2027.polling_system import (
            get_polling_system,
            get_user_polls,
            submit_vote,
            get_poll_display,
            get_results_display
        )

        ctx = message.user_context

        # Check if continuing a poll vote from flow_data
        poll_id = ctx.flow_data.get("active_poll")

        if poll_id:
            ps = get_polling_system()
            poll = ps.get_poll(poll_id)
            if poll:
                try:
                    choice = int(message.query) - 1
                    if 0 <= choice < len(poll.options):
                        option_id = poll.options[choice].id
                        success, vote_message = submit_vote(
                            poll_id, option_id, ctx.phone, ctx.state
                        )
                        if success:
                            results = get_results_display(poll_id)
                            return self.success(
                                f"{vote_message}\n\n{results}",
                                data={"clear_active_poll": True}
                            )
                        return self.success(vote_message)
                except ValueError:
                    pass

        # Start poll selection
        polls = get_user_polls(user_state=ctx.state, user_lga=ctx.lga)
        if polls:
            display = get_poll_display(polls[0].id)
            return self.success(display, data={"active_poll": polls[0].id})

        return self.success("No active polls right now. Check back soon! 📊")

    async def _handle_poll_results(self, message: AgentMessage) -> AgentResult:
        """Handle showing poll results."""
        from app.services.election_2027.polling_system import (
            get_polling_system,
            get_results_display
        )

        ps = get_polling_system()
        polls = ps.get_active_polls()

        if not polls:
            return self.success("No poll results available yet.")

        # Show most popular poll results
        main_poll = next(
            (p for p in polls if "president" in p.title.lower()),
            polls[0]
        )
        return self.success(get_results_display(main_poll.id))

    async def _handle_trending(self, message: AgentMessage) -> AgentResult:
        """Handle trending election topics."""
        from app.services.content_context_engine import get_content_engine

        content_engine = get_content_engine()
        hot_topics = content_engine.get_trending_today()

        text = "🔥 *Trending in Nigerian Politics*\n\n"
        for topic in hot_topics[:5]:
            text += f"• {topic['name']}: {topic['summary']}\n\n"
        text += "Ask about any topic for more details."

        return self.success(text)

    async def _handle_election_info(self, message: AgentMessage) -> AgentResult:
        """Handle general election information."""
        response = """🗳️ *2027 General Elections*

📅 *Key Dates:*
• Presidential/NASS: February 2027
• Governorship/State Assembly: March 2027

📌 *Current Status:*
• Campaign season begins: Late 2026
• Voter registration: Ongoing at INEC offices
• PVC collection: Check your INEC office

👥 *Key Candidates:*
• APC: President Tinubu (Incumbent)
• PDP: Atiku Abubakar (Expected)
• LP: Peter Obi (Expected)
• NNPP: Rabiu Kwankwaso (Expected)

Say 'who is running' for full candidate list.
Say 'follow [name]' to track a candidate."""

        return self.success(response)
