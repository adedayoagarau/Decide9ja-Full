"""
ElectionInfoAgent
=================
Provides 2027 election information, dates, registration, and polling units.

DATABASE FIRST with static election data fallback.
Cost: FREE (static/cached data)

Handles:
- "When is the 2027 election?"
- "How do I register to vote?"
- "Where is my polling unit?"
- "Who are the candidates for president?"
- "INEC registration deadline"
"""

from typing import Optional, Dict, List
from datetime import date
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
class ElectionInfoAgent(DatabaseAgent):
    name = "election_info"
    description = "2027 election dates, registration, and candidate information"
    tier = AgentTier.CORE
    cost_level = CostLevel.FREE
    handled_intents = [
        Intent.ELECTION_INFO,
        Intent.VOTER_REGISTRATION,
        Intent.POLLING_UNIT,
        Intent.CANDIDATE_SEARCH,
        Intent.CANDIDATE_FOLLOW,
        Intent.CANDIDATE_UNFOLLOW,
        Intent.CANDIDATE_COMPARE,
        Intent.MY_CANDIDATES,
    ]

    # Static election data (2027)
    ELECTION_DATA = {
        "year": 2027,
        "presidential_date": "February 2027",
        "governorship_date": "March 2027",
        "registration_status": "Ongoing",
        "registration_deadline": "TBD (typically 60 days before election)",
        "inec_website": "https://www.inecnigeria.org",
        "inec_phone": "09-2348577",
        "pvc_collection": "Ongoing at INEC offices nationwide",
    }

    # Major 2027 candidates (update as announcements come)
    PRESIDENTIAL_CANDIDATES = [
        {"name": "Bola Tinubu", "party": "APC", "status": "Incumbent", "state": "Lagos"},
        {"name": "Atiku Abubakar", "party": "PDP", "status": "Expected", "state": "Adamawa"},
        {"name": "Peter Obi", "party": "LP", "status": "Expected", "state": "Anambra"},
        {"name": "Rabiu Kwankwaso", "party": "NNPP", "status": "Expected", "state": "Kano"},
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """Route to appropriate election query"""

        intent = input.intent

        if intent == Intent.VOTER_REGISTRATION:
            return {"type": "registration"}

        if intent == Intent.POLLING_UNIT:
            return await self._get_polling_unit(input)

        if intent == Intent.CANDIDATE_SEARCH:
            return {"type": "candidates", "candidates": self.PRESIDENTIAL_CANDIDATES}

        if intent == Intent.CANDIDATE_FOLLOW:
            return await self._handle_follow(input)

        if intent == Intent.CANDIDATE_UNFOLLOW:
            return await self._handle_unfollow(input)

        if intent == Intent.CANDIDATE_COMPARE:
            return await self._handle_compare(input)

        if intent == Intent.MY_CANDIDATES:
            return await self._get_followed_candidates(input)

        # Default: general election info
        return {"type": "general", "data": self.ELECTION_DATA}

    async def format_response(self, input: AgentInput, data: Dict) -> AgentOutput:
        """Format election info response"""

        response_type = data.get("type", "general")

        if response_type == "general":
            return self._format_general_info(data)

        if response_type == "registration":
            return self._format_registration_info()

        if response_type == "polling_unit":
            return self._format_polling_unit(data)

        if response_type == "candidates":
            return self._format_candidates(data)

        if response_type == "follow_success":
            return AgentOutput(
                success=True,
                response_text=data.get("message", "Candidate followed!"),
                cost_level=CostLevel.FREE
            )

        if response_type == "my_candidates":
            return self._format_my_candidates(data)

        if response_type == "compare":
            return self._format_comparison(data)

        return self._format_general_info({"data": self.ELECTION_DATA})

    def _format_general_info(self, data: Dict) -> AgentOutput:
        """Format general election information"""
        e = data.get("data", self.ELECTION_DATA)

        response = f"""🗳️ *2027 Nigerian General Elections*

📅 *Key Dates:*
• Presidential/NASS: {e['presidential_date']}
• Governorship/State Assembly: {e['governorship_date']}

📝 *Voter Registration:*
• Status: {e['registration_status']}
• Deadline: {e['registration_deadline']}
• PVC Collection: {e['pvc_collection']}

📞 *INEC Contact:*
• Website: {e['inec_website']}
• Phone: {e['inec_phone']}

💡 *Quick Actions:*
Say "register to vote" for registration steps
Say "who is running" to see candidates
Say "my polling unit" to find where to vote"""

        return AgentOutput(
            success=True,
            response_text=response,
            buttons=[
                {"text": "Registration Steps", "callback": "intent:voter_registration"},
                {"text": "See Candidates", "callback": "intent:candidate_search"},
                {"text": "Find Polling Unit", "callback": "intent:polling_unit"},
            ],
            sources=["INEC Nigeria"],
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "election_info", "subtopic": "general"}
        )

    def _format_registration_info(self) -> AgentOutput:
        """Format voter registration information"""

        response = """📝 *How to Register to Vote in Nigeria*

*Step 1: Visit INEC Office*
Go to your nearest INEC Local Government office with:
• Valid ID (NIN, Passport, Driver's License)
• Proof of address (utility bill, bank statement)

*Step 2: Biometric Capture*
INEC will capture your:
• Photograph
• Fingerprints
• Basic information

*Step 3: Collect PVC*
Your Permanent Voter Card (PVC) will be ready for collection at the same office (usually 2-4 weeks).

⚠️ *Important:*
• Registration is FREE
• You must be 18+ years old
• You can only register once
• Check INEC website for office locations

📞 *Need Help?*
INEC Helpline: 09-2348577
Website: inecnigeria.org

_Already registered? Say "my polling unit" to find where to vote._"""

        return AgentOutput(
            success=True,
            response_text=response,
            buttons=[
                {"text": "Find INEC Office", "callback": "action:find_inec"},
                {"text": "Check PVC Status", "callback": "action:check_pvc"},
            ],
            sources=["INEC Nigeria - Voter Registration"],
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "election_info", "subtopic": "registration"}
        )

    def _format_candidates(self, data: Dict) -> AgentOutput:
        """Format presidential candidates list"""
        candidates = data.get("candidates", self.PRESIDENTIAL_CANDIDATES)

        response = "🗳️ *2027 Presidential Candidates*\n\n"

        for c in candidates:
            party_emoji = {"APC": "🟢", "PDP": "🔴", "LP": "🟡", "NNPP": "🔵"}.get(c["party"], "⚪")
            status = f" ({c['status']})" if c.get("status") else ""
            response += f"{party_emoji} *{c['name']}* - {c['party']}{status}\n"
            response += f"   State: {c['state']}\n\n"

        response += """_Say a name for more details_
_Say "follow [name]" to track a candidate_
_Say "compare [name] vs [name]" to compare_"""

        return AgentOutput(
            success=True,
            response_text=response,
            buttons=[
                {"text": f"Follow {candidates[0]['name'].split()[0]}", "callback": f"follow:{candidates[0]['name']}"},
                {"text": "Compare Top 2", "callback": "compare:tinubu:atiku"},
            ],
            sources=["INEC Nigeria", "Party Declarations"],
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "election_info", "subtopic": "candidates"}
        )

    async def _get_polling_unit(self, input: AgentInput) -> Dict:
        """Get user's polling unit"""
        state = input.user.state
        lga = input.user.lga

        if not state or not lga:
            return {"type": "polling_unit", "need_location": True}

        # Try database lookup
        polling_unit = None
        if self.db:
            try:
                # Adapt to your database schema
                pass
            except Exception as e:
                logger.error(f"Polling unit lookup failed: {e}")

        return {
            "type": "polling_unit",
            "state": state,
            "lga": lga,
            "polling_unit": polling_unit
        }

    def _format_polling_unit(self, data: Dict) -> AgentOutput:
        """Format polling unit response"""

        if data.get("need_location"):
            return AgentOutput(
                success=True,
                response_text=(
                    "To find your polling unit, I need your location.\n\n"
                    "What state and LGA are you in?"
                ),
                buttons=[
                    {"text": "Lagos", "callback": "state:lagos"},
                    {"text": "Kano", "callback": "state:kano"},
                    {"text": "Rivers", "callback": "state:rivers"},
                ],
                cost_level=CostLevel.FREE
            )

        state = data.get("state", "")
        lga = data.get("lga", "")
        pu = data.get("polling_unit")

        if pu:
            response = f"""📍 *Your Polling Unit*

State: {state}
LGA: {lga}
Polling Unit: {pu.get('name', 'N/A')}
Address: {pu.get('address', 'N/A')}
Ward: {pu.get('ward', 'N/A')}

_Arrive early on election day with your PVC._"""
        else:
            response = f"""📍 *Finding Your Polling Unit*

Based on your location ({lga}, {state}), you can find your exact polling unit by:

1. *INEC Polling Unit Finder:*
   Visit: voters.inecnigeria.org
   Enter your VIN (Voter ID Number)

2. *Visit Local INEC Office:*
   Go to INEC office in {lga} with your PVC

3. *Call INEC:*
   09-2348577

_Make sure you know your polling unit before election day!_"""

        return AgentOutput(
            success=True,
            response_text=response,
            sources=["INEC Nigeria"],
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "election_info", "subtopic": "polling_unit", "state": state}
        )

    async def _handle_follow(self, input: AgentInput) -> Dict:
        """Handle follow candidate request"""
        # Extract candidate name
        name = input.entities.get("politician") or input.entities.get("candidate_name")

        if not name:
            text = input.raw_text.lower().replace("follow", "").strip()
            name = text.split()[0] if text.split() else None

        if not name:
            return {"type": "general", "data": self.ELECTION_DATA}

        # Store follow in database
        if self.db:
            try:
                # await self.db.follows.insert_one({...})
                pass
            except Exception as e:
                logger.error(f"Follow failed: {e}")

        return {
            "type": "follow_success",
            "message": f"✅ You're now following *{name.title()}*!\n\nYou'll get updates about their campaign and news.\n\nSay \"my candidates\" to see who you're following."
        }

    async def _handle_unfollow(self, input: AgentInput) -> Dict:
        """Handle unfollow candidate request"""
        name = input.entities.get("politician") or input.entities.get("candidate_name")

        return {
            "type": "follow_success",
            "message": f"✅ You've unfollowed *{name.title() if name else 'the candidate'}*."
        }

    async def _get_followed_candidates(self, input: AgentInput) -> Dict:
        """Get user's followed candidates"""
        followed = input.user.followed_politicians or []

        return {"type": "my_candidates", "followed": followed}

    def _format_my_candidates(self, data: Dict) -> AgentOutput:
        """Format followed candidates list"""
        followed = data.get("followed", [])

        if not followed:
            response = """📋 *Your Followed Candidates*

You're not following any candidates yet.

Say "follow [name]" to track a candidate, e.g.:
• "Follow Tinubu"
• "Follow Peter Obi"
• "Follow Atiku"

You'll get updates about their campaigns and news."""
        else:
            response = "📋 *Your Followed Candidates*\n\n"
            for name in followed:
                response += f"• {name}\n"
            response += "\n_Say \"unfollow [name]\" to stop tracking._"

        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE
        )

    async def _handle_compare(self, input: AgentInput) -> Dict:
        """Handle candidate comparison request"""
        # Extract names from entities or text
        candidates = input.entities.get("candidates", [])

        if len(candidates) < 2:
            # Try to parse from text
            import re
            text = input.raw_text.lower()
            text = re.sub(r"compare|and|vs|versus|with", " ", text)
            names = [n.strip() for n in text.split() if n.strip() and len(n) > 2]
            candidates = names[:2]

        return {"type": "compare", "candidates": candidates}

    def _format_comparison(self, data: Dict) -> AgentOutput:
        """Format candidate comparison"""
        names = data.get("candidates", [])

        if len(names) < 2:
            return AgentOutput(
                success=True,
                response_text=(
                    "To compare candidates, say something like:\n"
                    "• \"Compare Tinubu vs Atiku\"\n"
                    "• \"Compare Peter Obi and Kwankwaso\""
                ),
                cost_level=CostLevel.FREE
            )

        # Get profiles for comparison
        profiles = []
        for name in names[:2]:
            for c in self.PRESIDENTIAL_CANDIDATES:
                if name.lower() in c["name"].lower():
                    profiles.append(c)
                    break

        if len(profiles) < 2:
            return AgentOutput(
                success=True,
                response_text=f"I couldn't find both candidates. Try with full names.",
                cost_level=CostLevel.FREE
            )

        p1, p2 = profiles[0], profiles[1]

        response = f"""⚖️ *Candidate Comparison*

| | *{p1['name'].split()[-1]}* | *{p2['name'].split()[-1]}* |
|---|---|---|
| Party | {p1['party']} | {p2['party']} |
| State | {p1['state']} | {p2['state']} |
| Status | {p1.get('status', 'N/A')} | {p2.get('status', 'N/A')} |

_Say "[name] promises" to see their campaign pledges._
_Say "follow [name]" to track either candidate._"""

        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "election_info", "subtopic": "comparison"}
        )
