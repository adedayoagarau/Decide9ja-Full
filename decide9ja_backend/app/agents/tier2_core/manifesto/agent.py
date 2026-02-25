"""
ManifestoAgent - Party manifesto lookup

Part of Tier 2 (Core Knowledge Agents) in the multi-agent architecture.
Provides access to party manifestos and policy positions.
"""

import logging
from typing import Dict, List, Optional, Any

from app.agents.base import DatabaseAgent, AgentInput, AgentOutput
from app.agents.registry import register_agent, registry

logger = logging.getLogger(__name__)


@register_agent
class ManifestoAgent(DatabaseAgent):
    """
    Party manifesto lookup agent.

    Features:
    - Supports all major Nigerian political parties
    - Topic-based manifesto filtering
    - WhatsApp-formatted responses with page references
    - Free tier (database lookup only)

    Cost: Free (no LLM calls)
    """

    name = "manifesto"
    description = "Look up party manifesto and policy positions"
    cost_type = "free"

    # Nigerian political parties
    PARTIES = {
        "APC": {
            "name": "All Progressives Congress",
            "color": "Green",
            "founded": 2013,
            "slogan": "Progress for All"
        },
        "PDP": {
            "name": "Peoples Democratic Party",
            "color": "Red/Green/White",
            "founded": 1998,
            "slogan": "Power to the People"
        },
        "LP": {
            "name": "Labour Party",
            "color": "Green/White",
            "founded": 2002,
            "slogan": "A New Nigeria is Possible"
        },
        "NNPP": {
            "name": "New Nigeria Peoples Party",
            "color": "Blue/Red",
            "founded": 2001,
            "slogan": "Rescue Nigeria"
        },
        "APGA": {
            "name": "All Progressives Grand Alliance",
            "color": "Green/White/Red",
            "founded": 2002,
            "slogan": "Building a New Nigeria"
        },
        "SDP": {
            "name": "Social Democratic Party",
            "color": "Green/White",
            "founded": 2018,
            "slogan": "Power to the People"
        },
        "ADC": {
            "name": "African Democratic Congress",
            "color": "Purple/Gold",
            "founded": 2005,
            "slogan": "Restoring Hope"
        },
        "YPP": {
            "name": "Young Progressives Party",
            "color": "Black/Gold",
            "founded": 2017,
            "slogan": "New Thinking for a New Generation"
        },
        "PRP": {
            "name": "Peoples Redemption Party",
            "color": "Red",
            "founded": 1978,
            "slogan": "Freedom for the Talakawa"
        },
        "AA": {
            "name": "Action Alliance",
            "color": "Orange/Black",
            "founded": 2005,
            "slogan": "Alliance of Hope"
        }
    }

    # Common manifesto topics
    TOPICS = [
        "education",
        "healthcare",
        "security",
        "economy",
        "infrastructure",
        "agriculture",
        "corruption",
        "youth",
        "women",
        "technology",
        "environment",
        "power",
        "housing",
        "jobs",
        "minimum wage"
    ]

    async def process(self, input: AgentInput) -> AgentOutput:
        """
        Process manifesto lookup request.

        Flow:
        1. Parse request to extract party and topic
        2. Fetch manifesto from cache
        3. Format for WhatsApp
        """
        try:
            parsed = self._parse_request(input.raw_text)
            party = parsed.get("party")
            topic = parsed.get("topic")

            # If no party specified, show available options
            if not party:
                party_list = self._format_party_list()
                return AgentOutput(
                    success=True,
                    response_text=(
                        "📜 *Which party's manifesto?*\n\n"
                        f"{party_list}\n\n"
                        "_Example: 'APC manifesto on education'_"
                    ),
                    agent_name=self.name
                )

            # Normalize party code
            party = party.upper()
            if party not in self.PARTIES:
                # Try to find by partial match
                matched_party = self._find_party(party)
                if matched_party:
                    party = matched_party
                else:
                    return AgentOutput(
                        success=False,
                        response_text=(
                            f"Party '{party}' not found.\n\n"
                            "Try: APC, PDP, LP, NNPP, APGA, SDP, ADC"
                        ),
                        agent_name=self.name
                    )

            party_info = self.PARTIES[party]

            # Get knowledge cache agent
            cache = registry.get("knowledge_cache")
            if not cache:
                # Fallback: Return basic party info
                return self._fallback_response(party, party_info, topic)

            # Fetch manifesto from cache
            try:
                manifesto = await cache.get_manifesto(party, topic)
            except Exception as e:
                logger.warning(f"Failed to fetch manifesto: {e}")
                manifesto = None

            if not manifesto:
                return self._no_manifesto_response(party, party_info, topic)

            # Format response
            response = self._format_manifesto_response(party, party_info, manifesto, topic)

            return AgentOutput(
                success=True,
                response_text=response,
                sources=[f"{party} Manifesto 2023"],
                agent_name=self.name,
                context={"party": party, "topic": topic}
            )

        except Exception as e:
            logger.error(f"Manifesto lookup failed: {e}")
            return AgentOutput(
                success=False,
                response_text="Something went wrong. Please try again.",
                agent_name=self.name
            )

    def _parse_request(self, message: str) -> Dict[str, Any]:
        """
        Extract party and topic from message.

        Returns:
            Dict with party and topic (or None for each)
        """
        message_lower = message.lower()

        # Find party
        party = None

        # Check for party codes/names
        for code, info in self.PARTIES.items():
            if code.lower() in message_lower:
                party = code
                break
            # Check full party name
            if info["name"].lower() in message_lower:
                party = code
                break

        # Common aliases
        aliases = {
            "labour": "LP",
            "labor": "LP",
            "obidient": "LP",
            "progressive": "APC",
            "democrat": "PDP",
            "peoples democratic": "PDP",
        }
        if not party:
            for alias, code in aliases.items():
                if alias in message_lower:
                    party = code
                    break

        # Find topic
        topic = None
        for t in self.TOPICS:
            if t in message_lower:
                topic = t
                break

        # Additional topic aliases
        topic_aliases = {
            "health": "healthcare",
            "school": "education",
            "university": "education",
            "hospital": "healthcare",
            "crime": "security",
            "police": "security",
            "army": "security",
            "military": "security",
            "money": "economy",
            "naira": "economy",
            "road": "infrastructure",
            "electricity": "power",
            "light": "power",
            "nepa": "power",
            "farm": "agriculture",
            "food": "agriculture",
            "employment": "jobs",
            "work": "jobs",
            "salary": "minimum wage",
            "wage": "minimum wage"
        }
        if not topic:
            for alias, mapped_topic in topic_aliases.items():
                if alias in message_lower:
                    topic = mapped_topic
                    break

        return {"party": party, "topic": topic}

    def _find_party(self, query: str) -> Optional[str]:
        """Try to find party by partial match"""
        query_lower = query.lower()
        for code, info in self.PARTIES.items():
            if query_lower in code.lower() or query_lower in info["name"].lower():
                return code
        return None

    def _format_party_list(self) -> str:
        """Format list of parties for display"""
        lines = []
        for code, info in list(self.PARTIES.items())[:7]:
            lines.append(f"• *{code}* - {info['name']}")
        return "\n".join(lines)

    def _format_manifesto_response(
        self,
        party: str,
        party_info: Dict,
        manifesto: List[Dict],
        topic: Optional[str]
    ) -> str:
        """Format manifesto for WhatsApp display"""
        response = f"📜 *{party_info['name']} Manifesto*"
        if topic:
            response += f" - {topic.title()}"
        response += "\n\n"

        for section in manifesto[:3]:
            response += f"*{section.get('title', 'Policy')}*"
            if section.get('page'):
                response += f" (p.{section['page']})"
            response += "\n"

            content = section.get('content', '')
            if len(content) > 300:
                content = content[:297] + "..."
            response += f"_{content}_\n\n"

        response += f"📎 _Source: {party} Manifesto 2023_"

        return response

    def _fallback_response(
        self,
        party: str,
        party_info: Dict,
        topic: Optional[str]
    ) -> AgentOutput:
        """Provide basic party info when manifesto not available"""
        response = f"📜 *{party_info['name']} ({party})*\n\n"
        response += f"• Founded: {party_info.get('founded', 'Unknown')}\n"
        response += f"• Slogan: _{party_info.get('slogan', 'N/A')}_\n\n"

        if topic:
            response += f"I don't have their specific {topic} policies yet.\n\n"
        else:
            response += "Full manifesto data coming soon.\n\n"

        response += "_Ask about specific topics: education, healthcare, security, economy_"

        return AgentOutput(
            success=True,
            response_text=response,
            agent_name=self.name,
            context={"party": party, "topic": topic}
        )

    def _no_manifesto_response(
        self,
        party: str,
        party_info: Dict,
        topic: Optional[str]
    ) -> AgentOutput:
        """Response when manifesto not found in cache"""
        response = f"📜 *{party_info['name']}*\n\n"

        if topic:
            response += f"I don't have {party}'s {topic} policy details yet.\n\n"
        else:
            response += f"I don't have {party}'s full manifesto data yet.\n\n"

        response += (
            "Our team is working on adding party manifestos.\n\n"
            "_Try asking about a specific candidate instead._"
        )

        return AgentOutput(
            success=True,
            response_text=response,
            agent_name=self.name,
            context={"party": party, "topic": topic, "manifesto_missing": True}
        )

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if this agent can handle the input"""
        message = input.raw_text.lower()

        manifesto_keywords = [
            "manifesto", "policy", "plan", "position",
            "what does", "party", "platform"
        ]

        # Check for party mentions
        has_party = any(
            code.lower() in message or info["name"].lower() in message
            for code, info in self.PARTIES.items()
        )

        has_keyword = any(kw in message for kw in manifesto_keywords)

        return has_party and has_keyword
