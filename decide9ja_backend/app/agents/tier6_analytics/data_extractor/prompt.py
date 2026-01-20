"""
DataExtractorAgent Prompts
==========================
LLM prompts for extracting structured data from news articles.

These prompts are optimized for:
- Nigerian political context
- Consistent JSON output
- Factual extraction (not opinion)
- Source attribution
"""

POLITICIAN_EXTRACTION_PROMPT = """Extract structured information about {politician_name} from these Nigerian news articles.

ARTICLES:
{articles}

Return a valid JSON object with this exact structure:
{{
    "name": "Full official name",
    "party": "Current political party (APC, PDP, LP, NNPP, etc.) or null",
    "current_position": "Current official role/position or null",
    "state_of_origin": "Nigerian state of origin or null",
    "age": null or number if mentioned,
    "education": ["List of educational qualifications mentioned"],
    "career_history": ["List of previous positions, most recent first"],
    "promises": [
        {{
            "promise_text": "Exact quote or paraphrase of what they promised",
            "topic": "education|healthcare|security|economy|infrastructure|agriculture|corruption|youth|technology|other",
            "date_made": "YYYY-MM-DD or null if unknown",
            "source_url": "URL where this was mentioned or null",
            "status": "pending|in_progress|kept|broken|unknown"
        }}
    ],
    "recent_news": [
        {{
            "headline": "News headline",
            "summary": "1-2 sentence summary",
            "date": "YYYY-MM-DD or null",
            "source": "Source name",
            "url": "Article URL or null",
            "sentiment": "positive|negative|neutral"
        }}
    ],
    "controversies": [
        {{
            "description": "Brief factual description",
            "date": "YYYY-MM-DD or null",
            "source_url": "URL or null"
        }}
    ],
    "social_media": {{
        "twitter": "handle without @ or null",
        "facebook": "page name or null",
        "instagram": "handle or null"
    }},
    "contact": {{
        "email": "email or null",
        "phone": "phone or null",
        "office_address": "address or null"
    }}
}}

EXTRACTION RULES:
1. Only include information EXPLICITLY stated in the articles
2. Use null for unknown/unmentioned information
3. For promises, only include specific commitments with context
4. For controversies, stick to facts - no speculation
5. Sentiment should reflect article tone, not your opinion
6. Dates should be ISO format (YYYY-MM-DD) when known
7. Maximum 5 items in promises, recent_news, and controversies arrays

Return ONLY the JSON object, no explanation."""


PROMISE_STATUS_PROMPT = """Determine if this political promise has been kept, broken, or is still in progress.

PROMISE: {promise_text}
MADE BY: {politician_name}
DATE MADE: {date_made}

RECENT NEWS ARTICLES:
{articles}

Based on the articles, determine the promise status.

Return a valid JSON object:
{{
    "status": "kept|broken|in_progress|unknown",
    "evidence": "Brief explanation (1-2 sentences) citing specific article evidence",
    "source_url": "URL of the most relevant article supporting this status, or null",
    "confidence": 0.0 to 1.0 (how confident based on evidence)
}}

STATUS DEFINITIONS:
- "kept": Clear evidence the promise was fulfilled
- "broken": Clear evidence the promise was not fulfilled or contradicted
- "in_progress": Evidence of partial progress or ongoing implementation
- "unknown": No relevant evidence in the articles

IMPORTANT:
- Base status ONLY on article evidence, not assumptions
- If evidence is contradictory, use "unknown" with lower confidence
- Be conservative - use "unknown" if unsure

Return ONLY the JSON object."""


NEWS_SUMMARY_PROMPT = """Summarize the key Nigerian political news from these articles about {topic}.

ARTICLES:
{articles}

Extract the most important news items.

Return a valid JSON object:
{{
    "news_items": [
        {{
            "headline": "Concise headline (max 100 chars)",
            "summary": "2-3 sentence summary of the news",
            "date": "YYYY-MM-DD or null",
            "source": "Source name",
            "url": "Article URL or null",
            "politicians_mentioned": ["List of politician names"],
            "topic": "education|healthcare|security|economy|infrastructure|agriculture|corruption|youth|technology|other",
            "sentiment": "positive|negative|neutral",
            "importance": "high|medium|low"
        }}
    ]
}}

RULES:
1. Maximum 10 news items
2. Prioritize by importance (elections, major policy, controversies)
3. Deduplicate - don't repeat the same story from different sources
4. Sentiment should be objective assessment of tone
5. Include all politicians mentioned by name

Return ONLY the JSON object."""


# Additional extraction prompts for specific use cases

CONTROVERSY_EXTRACTION_PROMPT = """Extract any controversies or allegations mentioned about {politician_name}.

ARTICLES:
{articles}

Return JSON:
{{
    "controversies": [
        {{
            "type": "corruption|misconduct|legal|policy|statement|other",
            "description": "Factual description of the controversy",
            "date": "YYYY-MM-DD or null",
            "status": "alleged|confirmed|denied|resolved|ongoing",
            "source": "Source name",
            "source_url": "URL"
        }}
    ]
}}

IMPORTANT:
- Only include controversies with credible sources
- Mark allegations clearly as "alleged"
- Do not include opinion or speculation
- Include politician's response if mentioned"""


PARTY_AFFILIATION_PROMPT = """Determine the current and historical party affiliations for {politician_name}.

ARTICLES:
{articles}

Return JSON:
{{
    "current_party": "Party name or null",
    "party_history": [
        {{
            "party": "Party name",
            "from_year": YYYY or null,
            "to_year": YYYY or null (null if current),
            "positions_held": ["List of positions in this party"]
        }}
    ],
    "defection_history": [
        {{
            "from_party": "Party left",
            "to_party": "Party joined",
            "year": YYYY,
            "reason": "Stated reason if mentioned"
        }}
    ]
}}"""


# Prompt templates for specific topics
TOPIC_PROMPTS = {
    "education": """Extract education-related promises, policies, and actions by {politician_name}:
- School building/renovation projects
- Teacher hiring/training programs
- Scholarship programs
- Curriculum changes
- University/polytechnic projects""",

    "healthcare": """Extract healthcare-related promises, policies, and actions by {politician_name}:
- Hospital building/renovation
- Equipment procurement
- Health insurance programs
- Doctor/nurse recruitment
- Disease control initiatives""",

    "security": """Extract security-related promises, policies, and actions by {politician_name}:
- Military/police deployments
- Security infrastructure
- Anti-terrorism efforts
- Community policing
- Equipment procurement""",

    "economy": """Extract economy-related promises, policies, and actions by {politician_name}:
- Fiscal policies
- Trade agreements
- Employment programs
- Business incentives
- Currency/monetary policy""",

    "infrastructure": """Extract infrastructure-related promises, policies, and actions by {politician_name}:
- Road construction/repair
- Power/electricity projects
- Water supply
- Railway projects
- Housing programs"""
}
