"""
Nigerian Politics Knowledge Module

Provides contextual knowledge about Nigerian politics, governance,
hot issues, and current affairs to enhance the chatbot's understanding.
"""
from datetime import datetime
from typing import Dict, List, Optional

# === NIGERIAN GOVERNANCE STRUCTURE ===
GOVERNANCE_STRUCTURE = {
    "executive": {
        "federal": {
            "president": "Head of State and Commander-in-Chief",
            "vice_president": "Deputy to the President",
            "ministers": "Cabinet members appointed by President, confirmed by Senate",
            "sgf": "Secretary to the Government of the Federation"
        },
        "state": {
            "governor": "Chief Executive of a state",
            "deputy_governor": "Deputy to the Governor",
            "commissioners": "State cabinet members"
        },
        "local": {
            "chairman": "Head of Local Government Area (LGA)",
            "councillors": "LGA legislative members"
        }
    },
    "legislative": {
        "senate": {
            "members": 109,
            "per_state": 3,
            "fct": 1,
            "leader": "Senate President"
        },
        "house_of_reps": {
            "members": 360,
            "leader": "Speaker of the House"
        },
        "state_assembly": {
            "leader": "Speaker of the State House of Assembly"
        }
    },
    "judiciary": {
        "supreme_court": "Highest court, final appellate jurisdiction",
        "court_of_appeal": "Appellate court",
        "federal_high_court": "Federal matters",
        "state_high_court": "State matters"
    }
}

# === CURRENT HOT ISSUES (Updated regularly) ===
HOT_ISSUES_2024_2025 = {
    "economy": {
        "fuel_subsidy": {
            "status": "Removed May 2023",
            "impact": "Fuel prices rose from ₦185 to ₦600+",
            "sentiment": "Mixed - some support reform, many struggle with costs",
            "key_players": ["Tinubu", "NNPC", "Labour unions"]
        },
        "naira_float": {
            "status": "Naira floated June 2023",
            "impact": "Depreciated from ₦460 to ₦1500+ per USD",
            "sentiment": "Generally negative due to inflation",
            "key_players": ["CBN", "Tinubu", "Cardoso (CBN Governor)"]
        },
        "inflation": {
            "status": "Over 30% as of late 2024",
            "impact": "High cost of living, food insecurity",
            "sentiment": "Very negative",
            "key_players": ["CBN", "FG", "NBS"]
        },
        "tax_reform": {
            "status": "Controversial tax reform bills in NASS",
            "impact": "Proposed changes to VAT distribution, FIRS",
            "sentiment": "Highly contested, North vs South divide",
            "key_players": ["Tinubu", "Taiwo Oyedele", "Northern Governors"]
        }
    },
    "security": {
        "banditry": {
            "regions": ["Northwest", "Northcentral"],
            "states": ["Zamfara", "Katsina", "Kaduna", "Niger", "Benue"],
            "sentiment": "Very negative, feeling of government failure"
        },
        "insurgency": {
            "regions": ["Northeast"],
            "groups": ["Boko Haram", "ISWAP"],
            "states": ["Borno", "Yobe", "Adamawa"],
            "sentiment": "Cautious optimism with military gains"
        },
        "kidnapping": {
            "status": "Nationwide crisis",
            "hotspots": ["Abuja-Kaduna highway", "Ondo", "Imo"],
            "sentiment": "Very negative"
        }
    },
    "politics": {
        "rivers_crisis": {
            "parties": ["Wike (FCT Minister, APC ally)", "Fubara (Governor, PDP)"],
            "status": "Ongoing political battle",
            "issues": ["LGA control", "Party structure", "State funds"],
            "sentiment": "Divided along loyalties"
        },
        "2027_elections": {
            "status": "Early positioning",
            "potential_candidates": ["Tinubu (incumbent)", "Atiku", "Obi", "Kwankwaso"],
            "issues": ["Performance assessment", "Coalition building"]
        },
        "party_defections": {
            "recent": [
                "PDP members to APC (various states)",
                "Labour Party internal crisis"
            ],
            "trend": "Movement toward ruling party"
        }
    },
    "governance": {
        "minimum_wage": {
            "status": "Increased to ₦70,000 in 2024",
            "implementation": "Varies by state",
            "sentiment": "Positive but seen as inadequate due to inflation"
        },
        "electricity_tariff": {
            "status": "Band A tariff increased significantly",
            "impact": "Higher bills for 'better' supply areas",
            "sentiment": "Negative"
        },
        "student_loans": {
            "status": "Launched 2024",
            "sentiment": "Positive but implementation challenges"
        }
    }
}

# === MAJOR POLITICAL FIGURES ===
KEY_POLITICAL_FIGURES = {
    "federal": {
        "Bola Tinubu": {
            "position": "President",
            "party": "APC",
            "since": "May 2023",
            "known_for": ["Lagos model", "Fuel subsidy removal", "Naira float"]
        },
        "Kashim Shettima": {
            "position": "Vice President",
            "party": "APC",
            "since": "May 2023",
            "known_for": ["Former Borno Governor", "Same-faith ticket"]
        },
        "Godswill Akpabio": {
            "position": "Senate President",
            "party": "APC",
            "known_for": ["Former Akwa Ibom Governor", "Controversial statements"]
        },
        "Tajudeen Abbas": {
            "position": "Speaker, House of Reps",
            "party": "APC"
        },
        "Nyesom Wike": {
            "position": "FCT Minister",
            "party": "PDP (but allied with APC)",
            "known_for": ["Rivers crisis", "Infrastructure projects", "Political godfather"]
        }
    },
    "opposition": {
        "Atiku Abubakar": {
            "party": "PDP",
            "position": "Former VP, Presidential candidate",
            "known_for": ["Multiple presidential bids", "Business interests"]
        },
        "Peter Obi": {
            "party": "Labour Party",
            "known_for": ["2023 election", "Obidient movement", "Former Anambra Governor"]
        },
        "Rabiu Kwankwaso": {
            "party": "NNPP",
            "known_for": ["Kwankwasiyya movement", "Former Kano Governor"]
        }
    }
}

# === NIGERIAN POLITICAL PARTIES ===
POLITICAL_PARTIES = {
    "APC": {
        "full_name": "All Progressives Congress",
        "status": "Ruling party",
        "ideology": "Progressive, center-right",
        "chair": "Abdullahi Ganduje"
    },
    "PDP": {
        "full_name": "Peoples Democratic Party",
        "status": "Main opposition",
        "ideology": "Center, big tent",
        "chair": "Umar Damagum (Acting)"
    },
    "LP": {
        "full_name": "Labour Party",
        "status": "Third force",
        "ideology": "Social democratic",
        "chair": "Julius Abure (disputed)"
    },
    "NNPP": {
        "full_name": "New Nigeria Peoples Party",
        "status": "Regional (Northwest)",
        "ideology": "Populist"
    }
}

# === SENTIMENT KEYWORDS ===
SENTIMENT_KEYWORDS = {
    "positive": [
        "improvement", "progress", "achievement", "success", "growth",
        "development", "reform", "investment", "infrastructure"
    ],
    "negative": [
        "crisis", "failure", "corruption", "hardship", "suffering",
        "inflation", "insecurity", "kidnapping", "poverty", "hunger"
    ],
    "neutral": [
        "policy", "decision", "announcement", "meeting", "bill",
        "proposal", "statement", "report"
    ]
}


def get_hot_issues_context() -> str:
    """Get formatted context about current hot issues for Claude."""
    context = """=== CURRENT NIGERIAN HOT ISSUES (2024-2025) ===

ECONOMY:
• Fuel Subsidy: Removed May 2023. Prices from ₦185 to ₦600+. Mixed sentiment.
• Naira: Floated June 2023. Fell from ₦460 to ₦1500+/USD. Very negative sentiment.
• Inflation: Over 30%. High cost of living. Very negative sentiment.
• Tax Reform: Controversial bills. North-South divide. Highly contested.

SECURITY:
• Banditry: Northwest crisis (Zamfara, Katsina, Kaduna). Negative sentiment.
• Insurgency: Northeast (Boko Haram, ISWAP). Some military progress.
• Kidnapping: Nationwide. Major roads unsafe. Very negative.

POLITICS:
• Rivers Crisis: Wike vs Fubara ongoing battle. Divided sentiment.
• 2027 Positioning: Early moves by major politicians.
• Party Defections: Movement toward ruling APC.

GOVERNANCE:
• Minimum Wage: Raised to ₦70,000 but seen as inadequate.
• Electricity: Band A tariff hike. Negative sentiment.
• Student Loans: New program, positive but implementation issues.

KEY FIGURES TO KNOW:
• Tinubu (President, APC) - Fuel subsidy removal, Naira float
• Wike (FCT Minister) - Rivers crisis, infrastructure
• Peter Obi (LP) - Obidient movement, opposition figure
• Atiku (PDP) - Main opposition figure
• Fubara (Rivers Governor) - Conflict with Wike
"""
    return context


def get_governance_context() -> str:
    """Get formatted context about Nigerian governance structure."""
    return """=== NIGERIAN GOVERNANCE STRUCTURE ===

FEDERAL LEVEL:
• President: Head of State and Government (Bola Tinubu)
• Vice President: Kashim Shettima
• Senate: 109 members (3 per state + 1 FCT). Led by Senate President Akpabio.
• House of Reps: 360 members. Led by Speaker Tajudeen Abbas.
• Supreme Court: Highest court, final appellate jurisdiction.

STATE LEVEL (36 states + FCT):
• Governor: Chief Executive of each state
• State House of Assembly: State legislators
• State High Court: State judicial matters

LOCAL LEVEL (774 LGAs):
• Chairman: Head of Local Government Area
• Councillors: LGA legislative members

MAJOR PARTIES:
• APC (All Progressives Congress) - Ruling party
• PDP (Peoples Democratic Party) - Main opposition
• LP (Labour Party) - Third force
• NNPP (New Nigeria Peoples Party) - Regional
"""


def analyze_query_for_hot_issues(query: str) -> Optional[Dict]:
    """
    Check if query relates to any hot issues and return context.

    Returns dict with issue details if found, None otherwise.
    """
    query_lower = query.lower()

    # Check economic issues
    if any(word in query_lower for word in ["subsidy", "fuel", "petrol", "diesel"]):
        return {
            "category": "economy",
            "issue": "fuel_subsidy",
            "context": HOT_ISSUES_2024_2025["economy"]["fuel_subsidy"],
            "search_terms": "Nigeria fuel subsidy Tinubu 2024"
        }

    if any(word in query_lower for word in ["naira", "dollar", "exchange", "forex", "currency"]):
        return {
            "category": "economy",
            "issue": "naira_float",
            "context": HOT_ISSUES_2024_2025["economy"]["naira_float"],
            "search_terms": "Nigeria naira exchange rate CBN 2024"
        }

    if any(word in query_lower for word in ["inflation", "prices", "cost of living", "expensive"]):
        return {
            "category": "economy",
            "issue": "inflation",
            "context": HOT_ISSUES_2024_2025["economy"]["inflation"],
            "search_terms": "Nigeria inflation rate cost of living 2024"
        }

    if any(word in query_lower for word in ["tax", "vat", "firs", "revenue"]):
        return {
            "category": "economy",
            "issue": "tax_reform",
            "context": HOT_ISSUES_2024_2025["economy"]["tax_reform"],
            "search_terms": "Nigeria tax reform bill controversy 2024"
        }

    # Check security issues
    if any(word in query_lower for word in ["bandit", "kidnap", "security", "insecurity"]):
        return {
            "category": "security",
            "issue": "general_security",
            "context": HOT_ISSUES_2024_2025["security"],
            "search_terms": "Nigeria security kidnapping banditry 2024"
        }

    if any(word in query_lower for word in ["boko haram", "iswap", "insurgent", "terrorism"]):
        return {
            "category": "security",
            "issue": "insurgency",
            "context": HOT_ISSUES_2024_2025["security"]["insurgency"],
            "search_terms": "Nigeria Boko Haram insurgency Northeast 2024"
        }

    # Check political issues
    if any(word in query_lower for word in ["wike", "fubara", "rivers"]):
        return {
            "category": "politics",
            "issue": "rivers_crisis",
            "context": HOT_ISSUES_2024_2025["politics"]["rivers_crisis"],
            "search_terms": "Wike Fubara Rivers State crisis 2024"
        }

    if any(word in query_lower for word in ["defect", "decamped", "joined apc", "left pdp"]):
        return {
            "category": "politics",
            "issue": "party_defections",
            "context": HOT_ISSUES_2024_2025["politics"]["party_defections"],
            "search_terms": "Nigeria politician defection party 2024"
        }

    if any(word in query_lower for word in ["minimum wage", "salary", "workers"]):
        return {
            "category": "governance",
            "issue": "minimum_wage",
            "context": HOT_ISSUES_2024_2025["governance"]["minimum_wage"],
            "search_terms": "Nigeria minimum wage implementation 2024"
        }

    if any(word in query_lower for word in ["electricity", "tariff", "nerc", "power"]):
        return {
            "category": "governance",
            "issue": "electricity",
            "context": HOT_ISSUES_2024_2025["governance"]["electricity_tariff"],
            "search_terms": "Nigeria electricity tariff Band A 2024"
        }

    return None


def get_politician_context(name: str) -> Optional[Dict]:
    """Get context about a politician if known."""
    name_lower = name.lower()

    # Check federal figures
    for person, details in KEY_POLITICAL_FIGURES["federal"].items():
        if person.lower() in name_lower or name_lower in person.lower():
            return {"name": person, **details, "category": "federal"}

    # Check opposition figures
    for person, details in KEY_POLITICAL_FIGURES["opposition"].items():
        if person.lower() in name_lower or name_lower in person.lower():
            return {"name": person, **details, "category": "opposition"}

    return None


def get_party_context(party: str) -> Optional[Dict]:
    """Get context about a political party."""
    party_upper = party.upper()

    if party_upper in POLITICAL_PARTIES:
        return {"code": party_upper, **POLITICAL_PARTIES[party_upper]}

    # Check full names
    for code, details in POLITICAL_PARTIES.items():
        if party.lower() in details["full_name"].lower():
            return {"code": code, **details}

    return None
