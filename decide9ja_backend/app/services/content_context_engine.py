"""
Content Context Engine

A real-time learning system that:
1. Fetches and processes Nigerian news continuously
2. Maps issues and relationships (tax → inflation → cost of living)
3. Tracks trending topics and sentiment
4. Provides context for intelligent responses

This is the brain that helps Tade understand Nigeria in real-time.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A news item with metadata."""
    title: str
    summary: str
    source: str
    url: str
    published: datetime
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    sentiment: str = "neutral"  # positive, negative, neutral

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "url": self.url,
            "published": self.published.isoformat(),
            "topics": self.topics,
            "entities": self.entities,
            "sentiment": self.sentiment
        }


@dataclass
class IssueContext:
    """Context for a political/economic issue."""
    name: str
    category: str
    status: str
    effective_date: Optional[str] = None
    impact: str = ""
    affected_groups: List[str] = field(default_factory=list)
    related_issues: List[str] = field(default_factory=list)
    key_players: List[str] = field(default_factory=list)
    sentiment: str = "mixed"
    simple_explanation: str = ""
    analogies: List[str] = field(default_factory=list)
    faqs: List[Dict] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


# === 2026 CURRENT ISSUES ===
# Updated for January 1, 2026

CURRENT_ISSUES_2026 = {
    # === THE 2026 TAX REFORM === (HOTTEST ISSUE - EFFECTIVE TODAY)
    "tax_reform_2026": IssueContext(
        name="2026 Tax Reform Laws",
        category="economy",
        status="EFFECTIVE TODAY (January 1, 2026)",
        effective_date="2026-01-01",
        impact="Major changes to how Nigerians and businesses pay taxes",
        affected_groups=[
            "All Nigerian workers",
            "Business owners (small and large)",
            "State governments (VAT sharing)",
            "Importers and exporters",
            "Digital businesses"
        ],
        related_issues=[
            "cost_of_living",
            "inflation",
            "state_revenue",
            "business_environment"
        ],
        key_players=[
            "President Tinubu",
            "Taiwo Oyedele (Tax Reform Committee)",
            "FIRS",
            "State Governors",
            "National Assembly"
        ],
        sentiment="highly_contested",
        simple_explanation="""
The 2026 Tax Reform is a big change in how Nigeria collects taxes. Think of it like this:

Before, taxes were like a pot of soup that was shared in a certain way between the Federal Government and States. Now, the recipe has changed - how the soup is shared is different, and some new ingredients (taxes) have been added.

Key changes:
1. VAT (the tax you pay when you buy things) sharing formula changed
2. New taxes on some digital services
3. Changes to how companies pay taxes
4. New rules for informal businesses

Some states are happy because they might get more money. Others are worried they might get less. Businesses are adjusting to new rules.
""",
        analogies=[
            "Think of VAT like adding a small tip every time you buy something. That tip goes to the government. Before, it was shared one way. Now it's shared differently.",
            "It's like when your compound changes how they share electricity bills - some flats pay more, some pay less, based on new calculations.",
            "Imagine a family where everyone contributes to buy food. The new tax law changes who contributes how much and who gets what portion.",
            "Like when DSTV changes their bouquet - some channels move, prices adjust, and you have to understand the new package."
        ],
        faqs=[
            {
                "q": "Will things become more expensive?",
                "a": "Some things might cost slightly more due to VAT adjustments, but the government says it's balancing it with other reliefs. Watch prices of your regular items in the coming weeks."
            },
            {
                "q": "Does this affect my salary?",
                "a": "If you're a formal worker (with payslip), your PAYE tax might be calculated slightly differently. Check with your HR or employer for specifics."
            },
            {
                "q": "What about small business owners?",
                "a": "Small businesses with turnover below certain thresholds may qualify for simplified tax rules. If you sell in the market or have a small shop, the impact depends on your annual sales."
            },
            {
                "q": "Why are some governors angry?",
                "a": "The way VAT revenue is shared between states has changed. States that generate more VAT (like Lagos) want to keep more of it. States that generate less are worried about losing money."
            }
        ]
    ),

    # === COST OF LIVING ===
    "cost_of_living": IssueContext(
        name="Cost of Living Crisis",
        category="economy",
        status="Ongoing - High inflation persists",
        impact="Everyday items more expensive, purchasing power reduced",
        affected_groups=["All Nigerians", "Low-income earners most affected"],
        related_issues=["naira_value", "fuel_prices", "food_prices", "tax_reform_2026"],
        key_players=["CBN", "FG", "Traders", "Manufacturers"],
        sentiment="very_negative",
        simple_explanation="""
Cost of living means how much money you need to survive - buy food, pay rent, transport, etc.

Right now in Nigeria, everything is expensive:
- A bag of rice that was ₦30,000 is now over ₦80,000
- Transport fare has more than doubled
- Rent keeps going up

Why? Multiple reasons working together like a chain:
1. Naira lost value → imports cost more
2. Fuel subsidy removed → transport costs up
3. Transport up → food prices up (to bring food to market)
4. Insecurity → farmers can't farm → less food → higher prices
""",
        analogies=[
            "It's like your salary stayed the same, but someone moved all the price tags up. Yesterday's ₦5,000 now buys what ₦2,000 used to buy.",
            "Imagine you have a bucket (your salary). The bucket didn't shrink, but everything you need to put in it got bigger. Now it doesn't fit.",
            "Like NEPA/PHCN - the units on your meter run faster than before, even though you're using the same appliances."
        ]
    ),

    # === NAIRA VALUE ===
    "naira_value": IssueContext(
        name="Naira Depreciation",
        category="economy",
        status="Naira trading around ₦1,500-1,800/USD",
        impact="Imports expensive, inflation high",
        affected_groups=["Importers", "Businesses", "Consumers", "Students abroad"],
        related_issues=["cost_of_living", "cbn_policies", "oil_prices"],
        key_players=["CBN Governor Cardoso", "President Tinubu", "Currency traders"],
        sentiment="negative",
        simple_explanation="""
The Naira is Nigeria's money. When we say it has "fallen" or "depreciated", it means you need more Naira to buy the same amount of Dollars or Pounds.

Before 2023: $1 = about ₦460
Now (2026): $1 = about ₦1,500-1,800

Why does this matter?
- Nigeria imports a lot (cars, phones, medicine, even food)
- When Naira falls, these imports cost more in Naira
- Shops increase prices → you pay more

It's like if bread was ₦500 but they started pricing it in dollars. If dollar goes up, your bread costs more even though nothing changed about the bread.
""",
        analogies=[
            "Think of Naira like our local currency at a market. If the market decides our money is worth less, we need more of it to buy the same tomatoes.",
            "It's like when your data bundle gives you less MB for the same price. Same ₦1,000, but less value.",
            "Imagine you're at Balogun market and suddenly all the traders want more money for the same goods because their suppliers charged them more."
        ]
    ),

    # === SECURITY ===
    "security": IssueContext(
        name="National Security Situation",
        category="security",
        status="Mixed - Some improvements, challenges remain",
        impact="Displacement, fear, economic disruption",
        affected_groups=["Farmers", "Travelers", "Northern residents", "Schools"],
        related_issues=["economy", "food_prices", "military_operations"],
        key_players=["NSA", "Military Chiefs", "State Governors", "Vigilante groups"],
        sentiment="mixed",
        simple_explanation="""
Nigeria faces different security challenges in different areas:

NORTH-EAST: Boko Haram/ISWAP terrorists - military fighting them, some progress
NORTH-WEST: Bandits kidnapping people, attacking villages - very serious
NORTH-CENTRAL: Farmer-herder clashes - ongoing tensions
SOUTH-EAST: IPOB/ESN activities - tensions continue
SOUTH-SOUTH: Oil theft and pipeline vandalism
EVERYWHERE: Kidnapping for ransom has become common

The government is trying different approaches - military operations, negotiations, state police discussions.
""",
        analogies=[
            "It's like different parts of a house having different problems - one room has leaking roof, another has broken window, another has faulty wiring. You need different solutions for each.",
            "Think of Nigeria as a big compound with different flats. Each flat has its own wahala, but it affects the whole compound."
        ]
    ),

    # === RIVERS CRISIS (CONTINUING) ===
    "rivers_crisis": IssueContext(
        name="Rivers State Political Crisis",
        category="politics",
        status="Ongoing - Wike vs Fubara battle continues",
        impact="Governance paralysis, LGA issues, political uncertainty",
        affected_groups=["Rivers State residents", "Civil servants", "Politicians"],
        related_issues=["2027_elections", "apc_pdp_dynamics"],
        key_players=["Nyesom Wike", "Siminalayi Fubara", "Rivers lawmakers"],
        sentiment="divided",
        simple_explanation="""
This is a power struggle between two men in Rivers State:

WIKE: Former Governor, now FCT Minister. Very powerful, has many loyal politicians.
FUBARA: Current Governor. Was Wike's accountant-general, Wike helped him become governor.

What happened?
They fell out after Fubara became governor. Wike wanted to keep controlling Rivers politics, Fubara wanted independence.

Now:
- They fight over who controls the State Assembly
- They fight over LGA chairmen
- Court cases everywhere
- Sometimes violence

It's like when Obi Cubana and his protégé have a public fight. The godfather (Wike) vs the godson (Fubara).
""",
        analogies=[
            "It's like a father who sponsored his son's business, then they quarreled and the father wants to take back the shop.",
            "Think of it like a football club owner fighting with the coach he appointed. The owner has money and connections, the coach has the players and fans.",
            "Like a master and apprentice story where the apprentice becomes successful and wants to be independent, but the master says 'I made you'."
        ]
    ),

    # === 2027 ELECTIONS ===
    "elections_2027": IssueContext(
        name="2027 General Elections",
        category="politics",
        status="Early positioning - still 18 months away",
        impact="Political realignments, policy focus shifts",
        affected_groups=["All voters", "Political parties", "Youth"],
        related_issues=["tinubu_performance", "opposition_unity", "electoral_reforms"],
        key_players=["President Tinubu", "Peter Obi", "Atiku", "Kwankwaso", "New faces"],
        sentiment="anticipation",
        simple_explanation="""
Nigeria's next big election is in February 2027. Though it's over a year away, politicians are already preparing:

QUESTIONS EVERYONE IS ASKING:
1. Will Tinubu run again? (Most likely yes)
2. Can the opposition unite? (They're trying to form alliance)
3. Will Peter Obi's movement maintain momentum?
4. Any new faces emerging?

WHAT TO WATCH:
- How people judge Tinubu's performance on economy
- Opposition party congresses and primaries
- Youth voter registration
- INEC preparations
"""
    ),

    # === MINIMUM WAGE ===
    "minimum_wage": IssueContext(
        name="Minimum Wage Implementation",
        category="economy",
        status="₦70,000 federal minimum wage, states struggling",
        impact="Workers' purchasing power, labor relations",
        affected_groups=["Civil servants", "Private sector workers", "State governments"],
        related_issues=["cost_of_living", "state_finances", "labor_unions"],
        key_players=["NLC", "TUC", "State Governors", "FG"],
        sentiment="mixed",
        simple_explanation="""
Minimum wage is the least amount an employer can legally pay a worker monthly.

Current situation (2026):
- Federal minimum wage: ₦70,000
- But with current prices, ₦70,000 can barely last a week for a family
- Many states haven't even fully implemented it
- Workers are asking for review

The challenge:
When ₦70,000 was announced, dollar was lower, fuel was cheaper. Now the same ₦70,000 buys much less. It's like getting a raise that's already outdated before you receive it.
""",
        analogies=[
            "It's like your landlord agreeing to reduce your rent, but by the time the agreement starts, everything else has increased so much that you're still struggling.",
            "Imagine you negotiate for a bigger bowl of rice, but by the time they serve you, rice has become so expensive that your 'bigger bowl' is actually smaller than your old one."
        ]
    )
}


# === ISSUE RELATIONSHIP MAP ===
# How issues connect to each other (for context building)

ISSUE_RELATIONSHIPS = {
    "tax_reform_2026": {
        "affects": ["cost_of_living", "state_revenue", "business_environment"],
        "affected_by": ["economy", "political_negotiations"],
        "related_to": ["vat", "firs", "state_finances"]
    },
    "cost_of_living": {
        "affects": ["poverty", "consumer_spending", "social_stability"],
        "affected_by": ["naira_value", "fuel_prices", "tax_reform_2026", "security"],
        "related_to": ["inflation", "minimum_wage", "food_prices"]
    },
    "naira_value": {
        "affects": ["import_prices", "cost_of_living", "foreign_investment"],
        "affected_by": ["cbn_policies", "oil_revenue", "forex_demand"],
        "related_to": ["dollar", "forex", "exchange_rate"]
    },
    "security": {
        "affects": ["farming", "investment", "tourism", "food_prices"],
        "affected_by": ["poverty", "governance", "military_capacity"],
        "related_to": ["banditry", "insurgency", "kidnapping"]
    }
}


# === KEYWORD TO ISSUE MAPPING ===
# Maps user keywords to relevant issues

KEYWORD_ISSUE_MAP = {
    # Tax related
    "tax": "tax_reform_2026",
    "vat": "tax_reform_2026",
    "firs": "tax_reform_2026",
    "tax reform": "tax_reform_2026",
    "new tax": "tax_reform_2026",
    "tax law": "tax_reform_2026",
    "oyedele": "tax_reform_2026",

    # Economy
    "expensive": "cost_of_living",
    "prices": "cost_of_living",
    "costly": "cost_of_living",
    "inflation": "cost_of_living",
    "cost of living": "cost_of_living",
    "hardship": "cost_of_living",

    # Naira
    "naira": "naira_value",
    "dollar": "naira_value",
    "exchange": "naira_value",
    "forex": "naira_value",
    "currency": "naira_value",

    # Security
    "kidnap": "security",
    "bandit": "security",
    "security": "security",
    "boko haram": "security",
    "terrorist": "security",
    "insecurity": "security",

    # Rivers
    "wike": "rivers_crisis",
    "fubara": "rivers_crisis",
    "rivers": "rivers_crisis",

    # Elections
    "election": "elections_2027",
    "2027": "elections_2027",
    "vote": "elections_2027",
    "campaign": "elections_2027",

    # Wages
    "salary": "minimum_wage",
    "minimum wage": "minimum_wage",
    "wage": "minimum_wage",
    "pay": "minimum_wage"
}


class ContentContextEngine:
    """
    The brain that helps Tade understand Nigeria in real-time.

    Functions:
    1. Identify relevant issues from user queries
    2. Provide context and relationships
    3. Generate simple explanations with analogies
    4. Fetch and process real-time news
    5. Track trending topics
    """

    def __init__(self):
        self.issues = CURRENT_ISSUES_2026
        self.relationships = ISSUE_RELATIONSHIPS
        self.keyword_map = KEYWORD_ISSUE_MAP
        self.news_cache: List[NewsItem] = []
        self.cache_expiry = timedelta(minutes=30)
        self.last_cache_update = datetime.min

    def identify_issues(self, query: str) -> List[str]:
        """Identify which issues a query relates to."""
        query_lower = query.lower()
        found_issues = set()

        # Check keyword map
        for keyword, issue in self.keyword_map.items():
            if keyword in query_lower:
                found_issues.add(issue)

        # Also check issue names directly
        for issue_key in self.issues.keys():
            if issue_key.replace("_", " ") in query_lower:
                found_issues.add(issue_key)

        return list(found_issues)

    def get_issue_context(self, issue_key: str) -> Optional[IssueContext]:
        """Get full context for an issue."""
        return self.issues.get(issue_key)

    def get_related_issues(self, issue_key: str) -> List[str]:
        """Get related issues for broader context."""
        if issue_key in self.relationships:
            rel = self.relationships[issue_key]
            related = set(rel.get("affects", []))
            related.update(rel.get("affected_by", []))
            related.update(rel.get("related_to", []))
            return list(related)
        return []

    def generate_simple_explanation(
        self,
        issue_key: str,
        user_context: Optional[Dict] = None
    ) -> str:
        """
        Generate a simple explanation with analogies.
        Adapts to user context if available.
        """
        issue = self.issues.get(issue_key)
        if not issue:
            return ""

        explanation = f"📌 *{issue.name}*\n\n"
        explanation += f"Status: {issue.status}\n\n"
        explanation += issue.simple_explanation.strip()

        # Add a random analogy
        if issue.analogies:
            import random
            analogy = random.choice(issue.analogies)
            explanation += f"\n\n💡 *Simple way to think about it:*\n{analogy}"

        return explanation

    def get_faqs(self, issue_key: str) -> List[Dict]:
        """Get FAQs for an issue."""
        issue = self.issues.get(issue_key)
        if issue:
            return issue.faqs
        return []

    def build_context_for_query(self, query: str) -> Dict:
        """
        Build comprehensive context for a user query.
        Returns all relevant information for response generation.
        """
        # Identify issues
        identified_issues = self.identify_issues(query)

        context = {
            "identified_issues": identified_issues,
            "primary_issue": None,
            "issue_details": [],
            "related_issues": [],
            "explanations": [],
            "analogies": [],
            "faqs": []
        }

        if not identified_issues:
            return context

        # Primary issue is the first one found
        primary = identified_issues[0]
        context["primary_issue"] = primary

        # Get details for all identified issues
        for issue_key in identified_issues:
            issue = self.get_issue_context(issue_key)
            if issue:
                context["issue_details"].append({
                    "key": issue_key,
                    "name": issue.name,
                    "status": issue.status,
                    "category": issue.category,
                    "impact": issue.impact,
                    "sentiment": issue.sentiment
                })
                context["explanations"].append(issue.simple_explanation)
                context["analogies"].extend(issue.analogies)
                context["faqs"].extend(issue.faqs)

        # Get related issues
        for issue_key in identified_issues:
            related = self.get_related_issues(issue_key)
            context["related_issues"].extend(related)
        context["related_issues"] = list(set(context["related_issues"]))

        return context

    async def fetch_latest_news(self, topic: str = None) -> List[Dict]:
        """Fetch latest news from Nigerian sources."""
        try:
            from app.services.realtime import fetch_rss_news, fetch_web_search

            news = []

            # Fetch from RSS
            rss_news = fetch_rss_news(topic=topic, limit=5)
            for item in rss_news:
                news.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "link": item.get("link", ""),
                    "type": "rss"
                })

            # Fetch from web search
            if topic:
                web_news = fetch_web_search(topic, limit=3)
                for item in web_news:
                    news.append({
                        "title": item.get("title", ""),
                        "summary": item.get("summary", ""),
                        "source": item.get("source", "Web"),
                        "link": item.get("link", ""),
                        "type": "web"
                    })

            return news

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []

    def format_context_for_claude(self, context: Dict) -> str:
        """Format context for Claude prompt."""
        if not context.get("identified_issues"):
            return ""

        formatted = "=== RELEVANT CONTEXT FROM CONTENT ENGINE ===\n\n"

        # Issue details
        for issue in context.get("issue_details", []):
            formatted += f"📌 ISSUE: {issue['name']}\n"
            formatted += f"   Status: {issue['status']}\n"
            formatted += f"   Category: {issue['category']}\n"
            formatted += f"   Impact: {issue['impact']}\n"
            formatted += f"   Public Sentiment: {issue['sentiment']}\n\n"

        # Simple explanation
        if context.get("explanations"):
            formatted += "📝 SIMPLE EXPLANATION:\n"
            formatted += context["explanations"][0][:500] + "\n\n"

        # Analogies for simple explanation
        if context.get("analogies"):
            formatted += "💡 ANALOGIES TO USE:\n"
            for i, analogy in enumerate(context["analogies"][:3], 1):
                formatted += f"{i}. {analogy}\n"
            formatted += "\n"

        # Related issues
        if context.get("related_issues"):
            formatted += f"🔗 Related issues: {', '.join(context['related_issues'][:5])}\n\n"

        return formatted


# === SINGLETON INSTANCE ===
_engine_instance = None

def get_content_engine() -> ContentContextEngine:
    """Get or create the content context engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ContentContextEngine()
    return _engine_instance


# === CONVENIENCE FUNCTIONS ===

def get_issue_explanation(query: str) -> str:
    """Quick function to get explanation for a query."""
    engine = get_content_engine()
    issues = engine.identify_issues(query)
    if issues:
        return engine.generate_simple_explanation(issues[0])
    return ""


def get_query_context(query: str) -> Dict:
    """Quick function to get full context for a query."""
    engine = get_content_engine()
    return engine.build_context_for_query(query)


def get_today_hot_topic() -> str:
    """Get the hottest topic for today (January 1, 2026)."""
    return """🔥 *TODAY'S HOT TOPIC: 2026 Tax Reform Takes Effect*

The new tax laws came into effect TODAY (January 1, 2026).

Key changes:
• New VAT sharing formula between Federal and States
• Changes to company tax calculations
• New rules for digital businesses
• Adjustments to personal income tax

What does this mean for you?
• Prices of some goods may adjust
• Businesses are updating their systems
• States will receive different VAT amounts

Have questions about how this affects you? Just ask!
"""
