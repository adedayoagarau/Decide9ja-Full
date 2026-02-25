"""
VotingRecordAgent - Legislative voting history

Part of Tier 2 (Core Knowledge Agents) in the multi-agent architecture.
Provides access to how legislators voted on key bills.
"""

import logging
import re
from typing import Dict, List, Optional, Any

from app.agents.base import DatabaseAgent, AgentInput, AgentOutput
from app.agents.registry import register_agent, registry

logger = logging.getLogger(__name__)


@register_agent
class VotingRecordAgent(DatabaseAgent):
    """
    Legislative voting history agent.

    Features:
    - Look up voting records for senators and representatives
    - Filter by bill topic or date range
    - Shows YES/NO/ABSTAIN votes with bill summaries
    - Free tier (database lookup only)

    Cost: Free (no LLM calls)
    """

    name = "voting_record"
    description = "Look up how legislators voted on bills"
    cost_type = "free"

    # Legislative positions
    LEGISLATIVE_POSITIONS = [
        "senator",
        "representative",
        "rep",
        "member",
        "house of representatives",
        "senate",
        "assembly",
        "lawmaker",
        "legislator"
    ]

    # Common name variations for key legislators
    NAME_ALIASES = {
        "akpabio": "Godswill Akpabio",
        "kalu": "Orji Uzor Kalu",
        "ndume": "Ali Ndume",
        "saraki": "Bukola Saraki",
        "lawan": "Ahmad Lawan",
        "gbajabiamila": "Femi Gbajabiamila",
        "abbas": "Tajudeen Abbas",
        "barau": "Barau Jibrin",
        "bamidele": "Opeyemi Bamidele",
        "dangote": "Jibrin Ibrahim",
    }

    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """Not used — handle() is overridden directly."""
        return None

    async def handle(self, input: AgentInput) -> AgentOutput:
        """
        Process voting record lookup request.

        Flow:
        1. Extract politician name from message
        2. Verify they are a legislator
        3. Fetch voting records from cache
        4. Format for WhatsApp
        """
        try:
            politician = self._extract_name(input.raw_text)

            if not politician:
                return AgentOutput(
                    success=False,
                    response_text=(
                        "Which legislator's voting record?\n\n"
                        "*Examples:*\n"
                        "• Voting record of Godswill Akpabio\n"
                        "• How did Ali Ndume vote?\n"
                        "• Bukola Saraki voting history"
                    ),
                    agent_name=self.name
                )

            # Normalize name using aliases
            politician = self._normalize_name(politician)

            # Get knowledge cache agent
            cache = registry.get("knowledge_cache")
            if not cache:
                return AgentOutput(
                    success=False,
                    response_text="Voting records service temporarily unavailable.",
                    agent_name=self.name
                )

            # Check if politician exists in cache
            try:
                profile = await cache.get_politician(politician)
            except Exception as e:
                logger.warning(f"Failed to fetch politician: {e}")
                profile = None

            if not profile:
                # Record cache miss
                try:
                    await cache.record_cache_miss(
                        query=input.raw_text,
                        intent="voting_record",
                        entity=politician
                    )
                except Exception as e:
                    logger.warning(f"Failed to record cache miss: {e}")

                return AgentOutput(
                    success=False,
                    response_text=(
                        f"I don't have data on *{politician}* yet.\n\n"
                        "_Try asking about a senator or representative._"
                    ),
                    agent_name=self.name
                )

            # Check if they are a legislator
            position = profile.get("data", {}).get("current_position", "")
            is_legislator = self._is_legislator(position)

            if not is_legislator:
                return AgentOutput(
                    success=True,
                    response_text=(
                        f"*{politician}* is not a legislator.\n\n"
                        f"Current position: _{position}_\n\n"
                        "Voting records are only available for senators and representatives."
                    ),
                    agent_name=self.name,
                    context={"politician": politician, "position": position}
                )

            # Get voting records from cache
            try:
                records = await cache.get_voting_records(politician)
            except Exception as e:
                logger.warning(f"Failed to fetch voting records: {e}")
                records = None

            if not records:
                return AgentOutput(
                    success=True,
                    response_text=(
                        f"🗳️ *Voting Record: {politician}*\n\n"
                        f"Position: _{position}_\n\n"
                        "No voting records found yet.\n\n"
                        "_Our team is working on adding National Assembly voting data._"
                    ),
                    agent_name=self.name,
                    context={"politician": politician, "no_records": True}
                )

            # Format response
            response = self._format_voting_records(politician, position, records)

            return AgentOutput(
                success=True,
                response_text=response,
                sources=["National Assembly Records"],
                agent_name=self.name,
                context={"politician": politician, "record_count": len(records)}
            )

        except Exception as e:
            logger.error(f"Voting record lookup failed: {e}")
            return AgentOutput(
                success=False,
                response_text="Something went wrong. Please try again.",
                agent_name=self.name
            )

    def _extract_name(self, message: str) -> Optional[str]:
        """
        Extract politician name from message.

        Removes common phrases and extracts the name.
        """
        message_lower = message.lower()

        # Remove common phrases
        removal_phrases = [
            "voting record of",
            "voting record for",
            "voting record",
            "voting history of",
            "voting history for",
            "voting history",
            "how did",
            "how has",
            "vote",
            "voted",
            "votes",
            "of",
            "for",
            "the",
            "senator",
            "representative",
            "rep",
            "hon",
            "honorable",
            "distinguished",
            "?",
            "!"
        ]

        cleaned = message_lower
        for phrase in removal_phrases:
            cleaned = cleaned.replace(phrase, " ")

        # Remove extra whitespace
        cleaned = " ".join(cleaned.split())
        cleaned = cleaned.strip()

        if not cleaned or len(cleaned) < 3:
            return None

        # Title case the result
        return cleaned.title()

    def _normalize_name(self, name: str) -> str:
        """Normalize name using aliases"""
        name_lower = name.lower().strip()

        # Check aliases
        for alias, full_name in self.NAME_ALIASES.items():
            if alias in name_lower:
                return full_name

        return name

    def _is_legislator(self, position: str) -> bool:
        """Check if position indicates a legislator"""
        if not position:
            return False

        position_lower = position.lower()
        return any(pos in position_lower for pos in self.LEGISLATIVE_POSITIONS)

    def _format_voting_records(
        self,
        politician: str,
        position: str,
        records: List[Dict]
    ) -> str:
        """Format voting records for WhatsApp display"""
        response = f"🗳️ *Voting Record: {politician}*\n"
        response += f"_{position}_\n\n"

        # Limit to 7 most recent records
        for record in records[:7]:
            vote = record.get("vote", "UNKNOWN").upper()

            # Vote emoji
            if vote in ("YES", "YEA", "AYE"):
                emoji = "✅"
            elif vote in ("NO", "NAY"):
                emoji = "❌"
            elif vote in ("ABSTAIN", "ABSTAINED"):
                emoji = "⏸️"
            elif vote in ("ABSENT", "EXCUSED"):
                emoji = "🚫"
            else:
                emoji = "❔"

            bill_name = record.get("bill_name", "Unknown Bill")
            if len(bill_name) > 50:
                bill_name = bill_name[:47] + "..."

            response += f"{emoji} *{bill_name}*\n"
            response += f"   {vote}"

            if record.get("date"):
                response += f" | {record['date']}"

            response += "\n"

            if record.get("summary"):
                summary = record["summary"]
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                response += f"   _{summary}_\n"

            response += "\n"

        # Add statistics if available
        total = len(records)
        if total > 7:
            response += f"_Showing 7 of {total} votes_\n\n"

        response += "📎 _Source: National Assembly Records_"

        return response

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if this agent can handle the input"""
        message = input.raw_text.lower()

        voting_keywords = [
            "voting record",
            "voting history",
            "how did",
            "voted for",
            "voted against",
            "vote on"
        ]

        return any(kw in message for kw in voting_keywords)
