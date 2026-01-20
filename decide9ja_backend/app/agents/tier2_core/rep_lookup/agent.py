"""
RepLookupAgent
==============
Find elected representatives for a location.

DATABASE FIRST - only uses LLM for natural language formatting.
Cost: FREE (database lookup)
"""

from typing import Optional, Dict, List
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
class RepLookupAgent(DatabaseAgent):
    name = "rep_lookup"
    description = "Find elected representatives for a location"
    tier = AgentTier.CORE
    cost_level = CostLevel.FREE  # Database lookup, no LLM
    handled_intents = [Intent.REP_LOOKUP]

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent == Intent.REP_LOOKUP

    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """Query the politician database for representatives"""

        # Get user's location
        state = input.user.state
        lga = input.user.lga

        if not state:
            # Need location - return special marker
            return {"need_location": True}

        # Get requested office type
        office = input.entities.get("office")

        reps = []

        if self.db:
            try:
                # Adapt these queries to your actual database schema

                if office == "senator" or not office:
                    # Get senators for state
                    senators = await self._find_politicians(
                        state=state,
                        office_type="senator"
                    )
                    reps.extend(senators)

                if office == "representative" or not office:
                    # Get House of Reps member for constituency
                    constituency = await self._get_constituency(state, lga)
                    if constituency:
                        house_reps = await self._find_politicians(
                            constituency=constituency,
                            office_type="representative"
                        )
                        reps.extend(house_reps)

                if office == "governor" or not office:
                    # Get governor
                    governors = await self._find_politicians(
                        state=state,
                        office_type="governor"
                    )
                    reps.extend(governors)

            except Exception as e:
                logger.error(f"Database query failed: {e}")

        # If no database or no results, use fallback data
        if not reps:
            reps = self._get_fallback_data(state, office)

        if not reps:
            return None

        return {
            "representatives": reps,
            "state": state,
            "lga": lga,
            "office_requested": office
        }

    async def format_response(self, input: AgentInput, data: Dict) -> AgentOutput:
        """Format database result into user-friendly response"""

        if data.get("need_location"):
            return AgentOutput(
                success=True,
                response_text=(
                    "To find your representatives, I need to know your location.\n\n"
                    "What state are you in?"
                ),
                data={"need": "location"},
                buttons=[
                    {"text": "Lagos", "callback": "state:lagos"},
                    {"text": "Abuja (FCT)", "callback": "state:fct"},
                    {"text": "Kano", "callback": "state:kano"},
                    {"text": "Rivers", "callback": "state:rivers"},
                ],
                cost_level=CostLevel.FREE
            )

        reps = data["representatives"]
        state = data["state"]
        office = data.get("office_requested")

        # Format as readable list
        if office:
            response_parts = [f"*Your {office.title()} in {state}:*\n"]
        else:
            response_parts = [f"*Your representatives in {state}:*\n"]

        for rep in reps:
            party = rep.get("party", "N/A")
            office_title = rep.get("office_title", rep.get("office_type", "Official"))
            name = rep.get("name", "Unknown")

            response_parts.append(
                f"\n*{name}* ({party})\n"
                f"_{office_title}_"
            )

            # Add contact if available
            if rep.get("phone"):
                response_parts.append(f"\nPhone: {rep['phone']}")
            if rep.get("email"):
                response_parts.append(f"\nEmail: {rep['email']}")

        response_text = "".join(response_parts)

        # Add follow-up options
        response_text += "\n\n_Say a name for more details, or \"my rep\" to see your House Rep._"

        # Buttons for more info
        buttons = []
        for rep in reps[:3]:  # Max 3 buttons
            short_name = rep.get("name", "Unknown").split()[0]
            buttons.append({
                "text": f"More on {short_name}",
                "callback": f"politician:{rep.get('id', rep.get('name'))}"
            })

        return AgentOutput(
            success=True,
            response_text=response_text,
            buttons=buttons,
            data={"representatives": reps},
            sources=[f"Decide9ja Database - {state} Officials"],
            cost_level=CostLevel.FREE,
            analytics_tags={
                "topic": "representation",
                "state": state,
                "reps_found": len(reps),
                "office_type": office
            }
        )

    async def _find_politicians(
        self,
        state: str = None,
        constituency: str = None,
        office_type: str = None
    ) -> List[Dict]:
        """
        Find politicians matching criteria.
        Adapt this to your actual database schema.
        """
        # Placeholder - implement based on your database
        # For SQLAlchemy:
        # query = select(Politician).where(
        #     Politician.state == state,
        #     Politician.current_office_type == office_type,
        #     Politician.is_active == True
        # )
        # result = await self.db.execute(query)
        # return [row._asdict() for row in result.scalars()]

        return []

    async def _get_constituency(self, state: str, lga: str) -> Optional[str]:
        """Map LGA to federal constituency"""
        if not self.db or not lga:
            return None

        # Placeholder - implement based on your constituency mapping
        return None

    def _get_fallback_data(self, state: str, office: str = None) -> List[Dict]:
        """
        Fallback data when database unavailable.
        Contains key officials - extend as needed.
        """
        # Sample data - replace with actual data
        FALLBACK_REPS = {
            "Lagos": [
                {
                    "name": "Babajide Sanwo-Olu",
                    "party": "APC",
                    "office_type": "governor",
                    "office_title": "Governor of Lagos State"
                },
                {
                    "name": "Solomon Olamilekan Adeola",
                    "party": "APC",
                    "office_type": "senator",
                    "office_title": "Senator, Lagos West"
                },
                {
                    "name": "Tokunbo Abiru",
                    "party": "APC",
                    "office_type": "senator",
                    "office_title": "Senator, Lagos East"
                },
            ],
            "FCT": [
                {
                    "name": "Nyesom Wike",
                    "party": "PDP",
                    "office_type": "minister",
                    "office_title": "FCT Minister"
                },
            ],
            "Rivers": [
                {
                    "name": "Siminalayi Fubara",
                    "party": "PDP",
                    "office_type": "governor",
                    "office_title": "Governor of Rivers State"
                },
            ],
        }

        reps = FALLBACK_REPS.get(state, [])

        if office:
            reps = [r for r in reps if r.get("office_type") == office]

        return reps
