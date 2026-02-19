"""
PromiseLookupAgent
==================
Tracks and reports on political promises made by Nigerian politicians.

Database-first approach:
1. Query promises database
2. Match to politician
3. Return status and evidence

Cost: FREE (database only) or CHEAP (if LLM summarization needed)

Handles:
- "What did Tinubu promise about fuel subsidy?"
- "Has the minimum wage promise been fulfilled?"
- "Track APC promises"
- "Compare promises vs achievements"
"""

from typing import Optional, Dict, List
from datetime import datetime
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
from app.database import SessionLocal, Politician
from sqlalchemy import func, or_
import json

logger = logging.getLogger(__name__)


@register_agent
class PromiseLookupAgent(BaseAgent):
    name = "promise_lookup"
    description = "Track and report on political promises"
    tier = AgentTier.CORE
    cost_level = CostLevel.FREE  # Database lookup
    handled_intents = [
        Intent.PROMISE_LOOKUP,
        Intent.PROMISE_STATUS,
        Intent.PROMISE_COMPARE,
    ]

    # Promise status categories
    STATUS_LABELS = {
        "fulfilled": "✅ Fulfilled",
        "in_progress": "🔄 In Progress",
        "not_started": "⏳ Not Started",
        "broken": "❌ Broken",
        "modified": "📝 Modified",
        "unknown": "❓ Status Unknown"
    }

    # Promise categories
    PROMISE_CATEGORIES = [
        "economy", "security", "education", "health",
        "infrastructure", "governance", "social", "foreign_policy"
    ]

    # Fallback promises data (when database unavailable)
    FALLBACK_PROMISES = {
        "tinubu": [
            {
                "promise": "Increase minimum wage to N100,000",
                "date_made": "2023-02-14",
                "status": "in_progress",
                "category": "economy",
                "evidence": "Minimum wage increased to N70,000 in 2024"
            },
            {
                "promise": "Remove fuel subsidy",
                "date_made": "2023-05-29",
                "status": "fulfilled",
                "category": "economy",
                "evidence": "Subsidy removed May 29, 2023"
            },
            {
                "promise": "Unify exchange rate",
                "date_made": "2023-02-14",
                "status": "in_progress",
                "category": "economy",
                "evidence": "CBN floated naira June 2023"
            },
            {
                "promise": "Security improvement within 6 months",
                "date_made": "2023-05-29",
                "status": "not_started",
                "category": "security",
                "evidence": "Security challenges persist"
            },
        ],
        "obi": [
            {
                "promise": "Move Nigeria from consumption to production",
                "date_made": "2022-07-01",
                "status": "unknown",
                "category": "economy",
                "evidence": "Campaign promise, not in office"
            },
        ],
        "atiku": [
            {
                "promise": "Restructure Nigeria",
                "date_made": "2022-05-28",
                "status": "unknown",
                "category": "governance",
                "evidence": "Campaign promise, not in office"
            },
        ],
    }

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # Check cache first
        cached = await self._check_cache(input)
        if cached:
            return self._tag_analytics(input, cached)

        # Extract politician and category from query
        politician = self._extract_politician(input)
        category = self._extract_category(input)

        # Try database first
        promises = await self._query_promises_database(politician, category)

        # Fallback to static data if database fails
        if not promises:
            promises = self._get_fallback_promises(politician, category)

        if promises:
            output = self._format_promises_response(input, promises, politician)
        else:
            output = self._format_no_promises_found(input, politician)

        # Cache results
        if output.success:
            await self._save_cache(input, output, ttl=3600)  # 1 hour cache

        return self._tag_analytics(input, output)

    def _extract_politician(self, input: AgentInput) -> Optional[str]:
        """Extract politician name from query"""
        # From entities
        politician = input.entities.get("politician")
        if politician:
            return politician.lower()

        # Search in text
        text_lower = input.raw_text.lower()
        known_politicians = ["tinubu", "obi", "atiku", "buhari", "jonathan"]
        for name in known_politicians:
            if name in text_lower:
                return name

        return None

    def _extract_category(self, input: AgentInput) -> Optional[str]:
        """Extract promise category from query"""
        text_lower = input.raw_text.lower()

        category_keywords = {
            "economy": ["economy", "economic", "naira", "dollar", "inflation", "wage", "subsidy", "fuel", "price"],
            "security": ["security", "crime", "bandit", "terrorism", "police", "army", "safe"],
            "education": ["education", "school", "university", "student", "teacher", "asuu"],
            "health": ["health", "hospital", "doctor", "healthcare", "medicine"],
            "infrastructure": ["road", "power", "electricity", "water", "bridge", "rail"],
            "governance": ["restructure", "devolution", "corruption", "reform"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return None

    async def _query_promises_database(
        self, politician: Optional[str], category: Optional[str]
    ) -> List[Dict]:
        """Query promises from database (via Politician.data_json)"""
        if not politician:
            return []

        session = SessionLocal()
        try:
            # Find the politician
            term = politician.lower()
            query = session.query(Politician).filter(
                or_(
                    func.lower(Politician.name).contains(term),
                    func.lower(Politician.slug).contains(term.replace(" ", "-"))
                )
            )
            p = query.first()
            
            if not p or not p.data_json:
                return []
                
            # Parse JSON
            try:
                data = json.loads(p.data_json)
                promises = data.get("promises", [])
                
                # Filter by category if needed
                if category:
                    promises = [
                        prom for prom in promises 
                        if prom.get("category", "").lower() == category.lower()
                    ]
                    
                return promises
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error(f"Promise database query failed: {e}")
            return []
        finally:
            session.close()

    def _get_fallback_promises(
        self, politician: Optional[str], category: Optional[str]
    ) -> List[Dict]:
        """Get fallback promises data"""
        if politician and politician in self.FALLBACK_PROMISES:
            promises = self.FALLBACK_PROMISES[politician]
            if category:
                promises = [p for p in promises if p["category"] == category]
            return promises

        # If no specific politician, return top promises from current president
        return self.FALLBACK_PROMISES.get("tinubu", [])[:3]

    def _format_promises_response(
        self, input: AgentInput, promises: List[Dict], politician: Optional[str]
    ) -> AgentOutput:
        """Format promises for display"""
        politician_name = politician.title() if politician else "Recent"

        response_parts = [f"📋 *{politician_name}'s Promise Tracker*\n"]

        # Group by status
        status_groups = {}
        for promise in promises:
            status = promise.get("status", "unknown")
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(promise)

        # Display fulfilled first, then in_progress, etc.
        status_order = ["fulfilled", "in_progress", "not_started", "broken", "modified", "unknown"]

        for status in status_order:
            if status in status_groups:
                label = self.STATUS_LABELS.get(status, status)
                response_parts.append(f"\n*{label}*")
                for promise in status_groups[status][:3]:  # Max 3 per status
                    text = promise.get("promise", "")
                    evidence = promise.get("evidence", "")
                    response_parts.append(f"• {text}")
                    if evidence:
                        response_parts.append(f"  _Evidence: {evidence}_")

        # Summary stats
        total = len(promises)
        fulfilled = len(status_groups.get("fulfilled", []))
        in_progress = len(status_groups.get("in_progress", []))

        response_parts.append(f"\n\n📊 *Summary*: {fulfilled}/{total} fulfilled, {in_progress} in progress")
        response_parts.append("\n_Ask about specific promises or categories for more details._")

        return AgentOutput(
            success=True,
            response_text="\n".join(response_parts),
            data={
                "promises": promises,
                "politician": politician,
                "total": total,
                "fulfilled": fulfilled
            },
            buttons=[
                {"text": "Economy Promises", "callback": f"promises:{politician}:economy"},
                {"text": "Security Promises", "callback": f"promises:{politician}:security"},
                {"text": "All Promises", "callback": f"promises:{politician}:all"},
            ],
            sources=["Decide9ja Promise Tracker", "News Analysis"],
            cost_level=CostLevel.FREE,
            analytics_tags={
                "topic": "promises",
                "politician": politician,
                "promises_found": len(promises)
            }
        )

    def _format_no_promises_found(self, input: AgentInput, politician: Optional[str]) -> AgentOutput:
        """Response when no promises found"""
        if politician:
            message = f"""📋 *Promise Tracker*

I don't have detailed promise tracking for *{politician.title()}* yet.

You can ask about:
• Tinubu's campaign promises
• Specific policy areas (economy, security, etc.)
• Promise fulfillment status

_We're continuously updating our promise database._"""
        else:
            message = """📋 *Promise Tracker*

To look up political promises, please specify:
• A politician's name (e.g., "Tinubu promises")
• A topic area (e.g., "economy promises")
• Or ask about specific promises

Example: "What did Tinubu promise about minimum wage?"
"""

        return AgentOutput(
            success=True,
            response_text=message,
            buttons=[
                {"text": "Tinubu Promises", "callback": "promises:tinubu"},
                {"text": "Economy Promises", "callback": "promises:all:economy"},
                {"text": "Security Promises", "callback": "promises:all:security"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={
                "topic": "promises",
                "result": "no_matches",
                "politician_query": politician
            }
        )
