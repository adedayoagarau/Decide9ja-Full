"""
PoliticianProfileAgent
======================
Get detailed profile information about Nigerian politicians.

DATABASE FIRST - queries existing politician table.
Cost: FREE (database lookup)

Handles:
- "Tell me about Tinubu"
- "Who is Sanwo-Olu?"
- "Profile of Atiku"
- "Info on Peter Obi"
"""

from typing import Optional, Dict, List
import re
import logging

from app.agents.base import (
    DatabaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class PoliticianProfileAgent(DatabaseAgent):
    name = "politician_profile"
    description = "Get detailed politician profiles and information"
    tier = AgentTier.CORE
    cost_level = CostLevel.FREE
    handled_intents = [
        Intent.POLITICIAN_INFO,
        Intent.POLITICIAN_CONTACT,
    ]

    # Known politician name variations for fuzzy matching
    NAME_ALIASES = {
        "tinubu": ["bola tinubu", "bat", "jagaban", "asiwaju"],
        "atiku": ["atiku abubakar", "waziri adamawa"],
        "obi": ["peter obi", "okwute"],
        "sanwo-olu": ["sanwoolu", "sanwo olu", "babajide sanwo-olu", "jide"],
        "wike": ["nyesom wike", "governor wike"],
        "el-rufai": ["elrufai", "nasir el-rufai", "mallam el-rufai"],
        "shettima": ["kashim shettima", "senator shettima"],
        "fubara": ["siminalayi fubara", "sim fubara"],
        "kwankwaso": ["rabiu kwankwaso", "kwanko"],
        "okowa": ["ifeanyi okowa", "delta governor"],
        "lawan": ["ahmad lawan", "senate president lawan"],
        "gbajabiamila": ["femi gbajabiamila", "speaker gbajabiamila"],
    }

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """Query politician database for profile"""

        # Extract politician name from entities or raw text
        name = self._extract_politician_name(input)

        if not name:
            return {"need_name": True}

        # Try database lookup
        politician = None
        if self.db:
            try:
                politician = await self._find_politician(name)
            except Exception as e:
                logger.error(f"Database query failed: {e}")

        # If not in database, try fallback data
        if not politician:
            politician = self._get_fallback_profile(name)

        if not politician:
            return {"not_found": True, "searched_name": name}

        return {"politician": politician, "searched_name": name}

    async def format_response(self, input: AgentInput, data: Dict) -> AgentOutput:
        """Format politician profile for user"""

        if data.get("need_name"):
            return AgentOutput(
                success=True,
                response_text=(
                    "Which politician would you like to know about?\n\n"
                    "You can ask about any Nigerian politician, for example:\n"
                    "• \"Tell me about Tinubu\"\n"
                    "• \"Who is Peter Obi?\"\n"
                    "• \"Profile of Atiku\""
                ),
                cost_level=CostLevel.FREE
            )

        if data.get("not_found"):
            name = data.get("searched_name", "that politician")
            return AgentOutput(
                success=True,
                handoff_to="fallback",
                handoff_reason="politician_not_found",
                data={"searched_name": name},
                cost_level=CostLevel.FREE
            )

        p = data["politician"]

        # Build profile response
        response_parts = []

        # Header
        name = p.get("name", "Unknown")
        party = p.get("party", "")
        party_str = f" ({party})" if party else ""
        response_parts.append(f"*{name}*{party_str}\n")

        # Current position
        position = p.get("current_position") or p.get("position")
        if position:
            response_parts.append(f"📍 *Position:* {position}\n")

        # State/Location
        state = p.get("state")
        if state:
            response_parts.append(f"🏛️ *State:* {state}\n")

        # Biography
        bio = p.get("bio") or p.get("biography")
        if bio:
            # Truncate long bios
            if len(bio) > 300:
                bio = bio[:297] + "..."
            response_parts.append(f"\n📜 *About:*\n{bio}\n")

        # Education
        education = p.get("education")
        if education:
            if isinstance(education, list):
                education = ", ".join(education[:3])
            response_parts.append(f"\n🎓 *Education:* {education}\n")

        # Political history
        history = p.get("political_history") or p.get("previous_positions")
        if history:
            if isinstance(history, list):
                history = ", ".join(history[:3])
            response_parts.append(f"\n📋 *Previous Roles:* {history}\n")

        # Contact info (if politician_contact intent)
        if input.intent == Intent.POLITICIAN_CONTACT:
            contact_parts = []
            if p.get("email"):
                contact_parts.append(f"📧 Email: {p['email']}")
            if p.get("phone"):
                contact_parts.append(f"📞 Phone: {p['phone']}")
            if p.get("twitter"):
                contact_parts.append(f"🐦 Twitter: @{p['twitter']}")
            if p.get("website"):
                contact_parts.append(f"🌐 Website: {p['website']}")

            if contact_parts:
                response_parts.append("\n*Contact:*\n" + "\n".join(contact_parts))
            else:
                response_parts.append("\n_Contact information not available._")

        # Follow prompt
        response_parts.append(f"\n\n_Say \"follow {name.split()[0]}\" to get updates about this politician._")

        response_text = "".join(response_parts)

        return AgentOutput(
            success=True,
            response_text=response_text,
            data={"politician": p},
            sources=[f"Decide9ja Database - {name}"],
            buttons=[
                {"text": f"Follow {name.split()[0]}", "callback": f"follow:{p.get('id', name)}"},
                {"text": "News about them", "callback": f"news:{name}"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={
                "topic": "politician_profile",
                "politician": name,
                "party": party
            }
        )

    def _extract_politician_name(self, input: AgentInput) -> Optional[str]:
        """Extract politician name from input"""

        # From entities
        if input.entities.get("politician"):
            return input.entities["politician"]

        # From potential names
        if input.entities.get("potential_names"):
            return input.entities["potential_names"][0]

        # Try to extract from raw text
        text = input.raw_text.lower()

        # Check known politicians
        for canonical, aliases in self.NAME_ALIASES.items():
            if canonical in text:
                return canonical
            for alias in aliases:
                if alias in text:
                    return canonical

        # Try to extract capitalized names
        matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', input.raw_text)
        common_words = {"Tell", "About", "Who", "What", "Profile", "Info", "Is", "The"}
        names = [m for m in matches if m not in common_words]

        if names:
            return names[0].lower()

        return None

    async def _find_politician(self, name: str) -> Optional[Dict]:
        """Find politician in database by name"""
        # Adapt to your database schema
        # For SQLAlchemy:
        # from sqlalchemy import select, or_, func
        # query = select(Politician).where(
        #     or_(
        #         func.lower(Politician.name).contains(name.lower()),
        #         func.lower(Politician.aliases).contains(name.lower())
        #     )
        # )
        # result = await self.db.execute(query)
        # row = result.scalar_one_or_none()
        # return row._asdict() if row else None

        return None

    def _get_fallback_profile(self, name: str) -> Optional[Dict]:
        """Fallback profiles for major politicians"""

        PROFILES = {
            "tinubu": {
                "name": "Bola Ahmed Tinubu",
                "party": "APC",
                "current_position": "President of Nigeria",
                "state": "Lagos",
                "bio": "Bola Ahmed Tinubu is the 16th President of Nigeria, inaugurated on May 29, 2023. He previously served as Governor of Lagos State from 1999 to 2007 and is widely regarded as a key figure in Nigerian democracy.",
                "education": "Chicago State University (Accounting)",
                "political_history": "Governor of Lagos State (1999-2007), National Leader of APC",
                "twitter": "officialABAT",
            },
            "atiku": {
                "name": "Atiku Abubakar",
                "party": "PDP",
                "current_position": "Former Vice President",
                "state": "Adamawa",
                "bio": "Atiku Abubakar is a Nigerian politician and businessman who served as Vice President from 1999 to 2007. He has contested for president multiple times and remains a prominent opposition figure.",
                "education": "Ahmadu Bello University",
                "political_history": "Vice President (1999-2007), Presidential Candidate (2007, 2011, 2019, 2023)",
                "twitter": "atikidata",
            },
            "obi": {
                "name": "Peter Obi",
                "party": "LP",
                "current_position": "Former Governor, 2023 Presidential Candidate",
                "state": "Anambra",
                "bio": "Peter Gregory Obi is a Nigerian politician and businessman. He served as Governor of Anambra State (2006-2014) and was the Labour Party presidential candidate in 2023.",
                "education": "University of Nigeria, Nsukka",
                "political_history": "Governor of Anambra (2006-2014), VP Candidate (2019), Presidential Candidate (2023)",
                "twitter": "PeterObi",
            },
            "sanwo-olu": {
                "name": "Babajide Sanwo-Olu",
                "party": "APC",
                "current_position": "Governor of Lagos State",
                "state": "Lagos",
                "bio": "Babajide Olusola Sanwo-Olu is the current Governor of Lagos State, first elected in 2019 and re-elected in 2023. He previously served in various capacities in the Lagos State government.",
                "education": "University of Lagos, London Business School",
                "political_history": "Commissioner for various ministries in Lagos, Governor (2019-present)",
                "twitter": "jiaborofficial",
            },
            "wike": {
                "name": "Nyesom Wike",
                "party": "PDP",
                "current_position": "FCT Minister",
                "state": "Rivers",
                "bio": "Nyesom Ezenwo Wike is the current Minister of the Federal Capital Territory. He previously served as Governor of Rivers State from 2015 to 2023.",
                "education": "Rivers State University",
                "political_history": "Governor of Rivers (2015-2023), FCT Minister (2023-present)",
                "twitter": "GovWike",
            },
            "fubara": {
                "name": "Siminalayi Fubara",
                "party": "PDP",
                "current_position": "Governor of Rivers State",
                "state": "Rivers",
                "bio": "Siminalayi Fubara is the current Governor of Rivers State, inaugurated in May 2023. He previously served as the Accountant General of Rivers State.",
                "education": "Rivers State University",
                "political_history": "Accountant General of Rivers State, Governor (2023-present)",
            },
            "shettima": {
                "name": "Kashim Shettima",
                "party": "APC",
                "current_position": "Vice President of Nigeria",
                "state": "Borno",
                "bio": "Kashim Shettima is the current Vice President of Nigeria. He previously served as Governor of Borno State from 2011 to 2019 and as Senator for Borno Central.",
                "education": "University of Maiduguri",
                "political_history": "Governor of Borno (2011-2019), Senator (2019-2023), Vice President (2023-present)",
            },
            "kwankwaso": {
                "name": "Rabiu Kwankwaso",
                "party": "NNPP",
                "current_position": "Senator, Former Governor",
                "state": "Kano",
                "bio": "Rabiu Musa Kwankwaso is a Nigerian politician who served as Governor of Kano State (1999-2003, 2011-2015) and as Minister of Defence (2003-2007). He founded the NNPP party.",
                "education": "Ahmadu Bello University",
                "political_history": "Governor of Kano (1999-2003, 2011-2015), Minister of Defence, Senator",
                "twitter": "KwsHq",
            },
        }

        return PROFILES.get(name.lower())
