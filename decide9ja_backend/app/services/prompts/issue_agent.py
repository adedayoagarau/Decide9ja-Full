"""
Issue Agent Prompt - News Analysis & Issue Extraction

Links to Source of Truth for:
- Nigerian politics knowledge (for entity recognition)
- Entity definitions (for structured extraction)
- Current context (for relevance assessment)

This agent handles:
- Analyzing news articles for political content
- Extracting structured issue data
- Categorizing by domain and severity
- Identifying mentioned politicians
"""

from typing import Dict, List, Optional
from app.services.prompts.source_of_truth import (
    get_sot_sections,
    SOTSection,
    build_agent_prompt,
    AgentPromptConfig
)


# =============================================================================
# ISSUE ANALYSIS TASK
# =============================================================================

ISSUE_ANALYSIS_TASK = """
<task>
You are the Issue Agent for Decide9ja. Your job is to:

1. ANALYZE news articles about Nigerian politics
2. EXTRACT structured issue data
3. CATEGORIZE by domain and severity
4. IDENTIFY politicians and entities mentioned
5. ASSESS relevance to users

<input>
- News article (title, content, source, date)
</input>

<processing>
1. Read the article carefully
2. Identify the main political issue(s)
3. Extract all mentioned politicians and parties
4. Categorize by domain (security, economy, governance, etc.)
5. Assess severity and user relevance
6. Generate searchable tags
</processing>
</task>
"""

ISSUE_ANALYSIS_OUTPUT = """
<output_format>
Return JSON with this schema:

```json
{
  "title": "<concise issue title>",
  "summary": "<2-3 sentence summary>",
  "domain": "<domain_code>",
  "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "politicians_mentioned": [
    {
      "name": "<politician name>",
      "role": "<their role in the issue>",
      "party": "<party if known>"
    }
  ],
  "parties_mentioned": ["<party1>", "<party2>"],
  "states_affected": ["<state1>", "<state2>"],
  "entities": {
    "organizations": ["<org1>", "<org2>"],
    "locations": ["<loc1>", "<loc2>"],
    "amounts": ["<amount1>"]
  },
  "user_relevance": {
    "who_affected": "<who this affects>",
    "why_matters": "<why users should care>",
    "action_items": ["<what users can do>"]
  },
  "tags": ["<tag1>", "<tag2>", "<tag3>"],
  "sentiment": "positive|negative|neutral|mixed",
  "is_verified": false,
  "confidence": 0.0-1.0
}
```

<domain_codes>
| Code | Description | Keywords |
|------|-------------|----------|
| SECURITY | Crime, terrorism, banditry, kidnapping | police, army, attack, kidnap |
| ECONOMY | Budget, inflation, naira, trade | economy, budget, inflation, naira |
| GOVERNANCE | Government decisions, policies | policy, law, bill, executive |
| ELECTION | Elections, campaigns, INEC | election, vote, INEC, campaign |
| CORRUPTION | Fraud, embezzlement, scandal | corrupt, fraud, EFCC, scandal |
| INFRASTRUCTURE | Roads, power, water, housing | road, NEPA, power, infrastructure |
| EDUCATION | Schools, universities, ASUU | education, university, ASUU, school |
| HEALTH | Healthcare, epidemics, hospitals | health, hospital, disease, medical |
| JUDICIARY | Courts, legal matters | court, judge, ruling, lawsuit |
| POLITICS | Party matters, political moves | party, defection, coalition |
</domain_codes>

<severity_criteria>
- CRITICAL: National emergency, mass casualties, immediate action needed
- HIGH: Significant national impact, affects many people
- MEDIUM: Regional impact, notable but not urgent
- LOW: Local issue, limited impact
</severity_criteria>
</output_format>
"""

ISSUE_ANALYSIS_EXAMPLES = """
<examples>

<example>
ARTICLE:
Title: "Northern Governors Reject VAT Sharing Formula in Tax Reform Bill"
Content: "The Northern Governors Forum, led by Katsina Governor Dikko Radda, has rejected
the proposed VAT sharing formula in President Tinubu's Tax Reform Bills. They argue the
formula favors Lagos and Rivers at the expense of Northern states. The governors held an
emergency meeting in Kaduna on Monday..."
Source: Premium Times
Date: 2025-12-15

OUTPUT:
{
  "title": "Northern Governors Oppose Tax Reform VAT Formula",
  "summary": "Northern Governors Forum rejects proposed VAT sharing formula in Tinubu's Tax Reform Bills, claiming it unfairly favors Southern states like Lagos and Rivers.",
  "domain": "GOVERNANCE",
  "severity": "HIGH",
  "politicians_mentioned": [
    {
      "name": "Dikko Radda",
      "role": "Leading opposition to VAT formula",
      "party": "APC"
    },
    {
      "name": "Bola Ahmed Tinubu",
      "role": "Proposed the Tax Reform Bills",
      "party": "APC"
    }
  ],
  "parties_mentioned": ["APC"],
  "states_affected": ["All 36 states", "Lagos", "Rivers", "Katsina"],
  "entities": {
    "organizations": ["Northern Governors Forum", "National Assembly"],
    "locations": ["Kaduna"],
    "amounts": []
  },
  "user_relevance": {
    "who_affected": "All Nigerians - VAT affects prices of goods",
    "why_matters": "The outcome will determine how tax revenue is shared between states",
    "action_items": ["Follow the debate in National Assembly", "Understand how your state benefits or loses"]
  },
  "tags": ["tax reform", "VAT", "Northern Governors", "Tinubu", "fiscal federalism"],
  "sentiment": "negative",
  "is_verified": false,
  "confidence": 0.9
}
</example>

<example>
ARTICLE:
Title: "Bandits Kill 30 in Zamfara Attack"
Content: "Armed bandits have attacked three villages in Zamfara State, killing at least
30 people and displacing hundreds. The attack occurred in Shinkafi Local Government Area
on Saturday night. Governor Dauda Lawal has ordered security reinforcement..."
Source: Daily Trust
Date: 2025-12-14

OUTPUT:
{
  "title": "Bandits Attack Zamfara Villages, 30 Dead",
  "summary": "Armed bandits killed 30 people in attacks on three villages in Shinkafi LGA, Zamfara State. Governor Dauda Lawal has ordered security reinforcement.",
  "domain": "SECURITY",
  "severity": "CRITICAL",
  "politicians_mentioned": [
    {
      "name": "Dauda Lawal",
      "role": "Responding to security crisis",
      "party": "PDP"
    }
  ],
  "parties_mentioned": ["PDP"],
  "states_affected": ["Zamfara"],
  "entities": {
    "organizations": ["Nigerian Army", "Police"],
    "locations": ["Shinkafi LGA", "Zamfara State"],
    "amounts": ["30 killed", "hundreds displaced"]
  },
  "user_relevance": {
    "who_affected": "Zamfara residents, Northwest Nigeria citizens",
    "why_matters": "Ongoing banditry crisis affecting security and livelihoods",
    "action_items": ["Stay informed about security situation", "Report suspicious activities"]
  },
  "tags": ["banditry", "Zamfara", "security", "Northwest", "violence"],
  "sentiment": "negative",
  "is_verified": false,
  "confidence": 0.85
}
</example>

<example>
ARTICLE:
Title: "Peter Obi Visits Atiku, Sparks 2027 Coalition Talks"
Content: "Labour Party presidential candidate Peter Obi paid a visit to former Vice
President Atiku Abubakar at his Abuja residence on Tuesday. Sources say they discussed
a possible opposition coalition ahead of the 2027 elections..."
Source: Vanguard
Date: 2025-12-16

OUTPUT:
{
  "title": "Peter Obi Meets Atiku Amid 2027 Coalition Speculation",
  "summary": "LP's Peter Obi visited Atiku Abubakar in Abuja, fueling speculation about opposition coalition talks ahead of 2027 elections.",
  "domain": "ELECTION",
  "severity": "MEDIUM",
  "politicians_mentioned": [
    {
      "name": "Peter Obi",
      "role": "Potential coalition partner",
      "party": "LP"
    },
    {
      "name": "Atiku Abubakar",
      "role": "Potential coalition partner",
      "party": "PDP"
    }
  ],
  "parties_mentioned": ["LP", "PDP"],
  "states_affected": [],
  "entities": {
    "organizations": ["Labour Party", "PDP"],
    "locations": ["Abuja"],
    "amounts": []
  },
  "user_relevance": {
    "who_affected": "Voters interested in 2027 elections",
    "why_matters": "Opposition coalition could reshape 2027 election dynamics",
    "action_items": ["Follow 2027 campaign developments", "Research candidates' positions"]
  },
  "tags": ["2027 election", "Peter Obi", "Atiku", "coalition", "opposition"],
  "sentiment": "neutral",
  "is_verified": false,
  "confidence": 0.8
}
</example>

</examples>
"""


# =============================================================================
# POLITICAL DATA AGENT TASK (Daily Intelligence)
# =============================================================================

DAILY_INTELLIGENCE_TASK = """
<task>
You are the Political Data Agent for Decide9ja, handling DAILY INTELLIGENCE.

Your job is to:
1. Process a batch of news articles
2. Identify trending topics and themes
3. Track politician mentions and sentiment
4. Detect emerging issues
5. Generate daily briefing

<input>
- List of analyzed issues from today
- Previous day's trending topics (for comparison)
</input>

<output>
- Daily trending topics
- Politician mention counts and sentiment
- Emerging vs continuing issues
- Key events summary
</output>
</task>
"""

DAILY_INTELLIGENCE_OUTPUT = """
<output_format>
Return JSON:

```json
{
  "date": "<YYYY-MM-DD>",
  "trending_topics": [
    {
      "topic": "<topic name>",
      "mention_count": 5,
      "trend": "rising|stable|falling",
      "key_articles": ["<title1>", "<title2>"]
    }
  ],
  "politician_tracker": [
    {
      "name": "<politician>",
      "mentions": 10,
      "sentiment_avg": 0.5,
      "contexts": ["tax reform", "security"]
    }
  ],
  "key_events": [
    {
      "event": "<event description>",
      "domain": "<domain>",
      "impact": "<HIGH|MEDIUM|LOW>"
    }
  ],
  "daily_summary": "<3-4 sentence summary of the day's political news>"
}
```
</output_format>
"""


# =============================================================================
# BUILD ISSUE AGENT PROMPTS
# =============================================================================

def build_issue_analysis_prompt(
    title: str,
    content: str,
    source: str,
    date: str
) -> str:
    """
    Build prompt for analyzing a news article.

    Args:
        title: Article title
        content: Article body text
        source: News source name
        date: Publication date
    """
    config = AgentPromptConfig(
        agent_name="Issue Agent (News Analyzer)",
        agent_role="Political News Analysis & Issue Extraction",
        sot_sections=[
            SOTSection.POLITICS,
            SOTSection.ENTITIES,
            SOTSection.CURRENT,
        ],
        task_specific=ISSUE_ANALYSIS_TASK,
        output_format=ISSUE_ANALYSIS_OUTPUT,
        examples=ISSUE_ANALYSIS_EXAMPLES
    )

    base_prompt = build_agent_prompt(config)

    # Truncate content if too long
    max_content_length = 3000
    if len(content) > max_content_length:
        content = content[:max_content_length] + "... [truncated]"

    query_section = f"""
<article_to_analyze>
TITLE: {title}
SOURCE: {source}
DATE: {date}

CONTENT:
{content}
</article_to_analyze>

INSTRUCTIONS:
Analyze this news article and extract structured issue data. Return ONLY the JSON output.
Focus on:
1. Identifying the core political issue
2. Extracting all mentioned politicians and their roles
3. Categorizing correctly by domain
4. Assessing real impact on Nigerian citizens
"""

    return base_prompt + query_section


def build_daily_intelligence_prompt(
    analyzed_issues: List[Dict],
    previous_trending: List[str] = None
) -> str:
    """
    Build prompt for daily intelligence summary.

    Args:
        analyzed_issues: List of already-analyzed issues from today
        previous_trending: Yesterday's trending topics for comparison
    """
    config = AgentPromptConfig(
        agent_name="Political Data Agent (Daily Intelligence)",
        agent_role="Daily Political Intelligence Aggregation",
        sot_sections=[SOTSection.CURRENT],
        task_specific=DAILY_INTELLIGENCE_TASK,
        output_format=DAILY_INTELLIGENCE_OUTPUT,
        examples=""
    )

    base_prompt = build_agent_prompt(config)

    # Format issues
    issues_text = "\n".join([
        f"- [{i['domain']}] {i['title']} (Severity: {i['severity']})"
        for i in analyzed_issues[:20]  # Limit to 20
    ])

    previous_text = ", ".join(previous_trending) if previous_trending else "None"

    query_section = f"""
<daily_data>
TODAY'S ANALYZED ISSUES:
{issues_text}

YESTERDAY'S TRENDING TOPICS:
{previous_text}
</daily_data>

INSTRUCTIONS:
Generate a daily intelligence summary. Identify:
1. What topics are trending (mentioned multiple times)
2. Which politicians are in the news most
3. Any emerging issues vs continuing stories
4. Overall sentiment of the day's news

Return ONLY the JSON output.
"""

    return base_prompt + query_section


# =============================================================================
# SIMILAR ISSUE DETECTION
# =============================================================================

def build_similarity_prompt(
    new_issue: Dict,
    existing_issues: List[Dict]
) -> str:
    """
    Build prompt to find similar existing issues.

    Args:
        new_issue: The newly extracted issue
        existing_issues: List of existing issues to compare against
    """
    existing_text = "\n".join([
        f"[ID:{i.get('id', idx)}] {i['title']} - {i['summary'][:100]}"
        for idx, i in enumerate(existing_issues[:10])
    ])

    return f"""<task>
Find if this new issue is similar to any existing issues.

NEW ISSUE:
Title: {new_issue['title']}
Summary: {new_issue['summary']}
Domain: {new_issue['domain']}

EXISTING ISSUES:
{existing_text}

INSTRUCTIONS:
Return JSON with similar issue IDs and similarity scores (0-1):
{{
  "similar_issues": [
    {{"id": "...", "similarity": 0.8, "reason": "same topic"}}
  ],
  "is_duplicate": false,
  "merge_suggestion": null
}}

A duplicate is >0.9 similarity. Similar is >0.6.
</task>"""
