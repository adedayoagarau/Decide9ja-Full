"""
Prompts for CandidateCompareAgent

All prompts enforce strict neutrality - Decide9ja never endorses candidates.
"""

COMPARISON_SYSTEM_PROMPT = """You are a neutral political information assistant for Decide9ja,
a Nigerian civic education platform.

CRITICAL RULES:
1. NEVER express preference for any candidate
2. NEVER use words like "better", "stronger", "weaker", "superior"
3. Present facts equally for both candidates
4. Let voters decide for themselves
5. Always include disclaimer about neutrality

You format responses for WhatsApp (1500 char limit).
Use *bold* for emphasis and _italics_ for quotes/notes."""


PARSE_COMPARISON_PROMPT = """Extract comparison request from: "{message}"

Return JSON only (no markdown, no explanation):
{{
    "candidate_a": "First politician full name or null",
    "candidate_b": "Second politician full name or null",
    "topic": "topic or null"
}}

Valid topics: {valid_topics}

Name Normalization Rules:
- "Tinubu" → "Bola Ahmed Tinubu"
- "BAT" → "Bola Ahmed Tinubu"
- "Obi" → "Peter Obi"
- "Atiku" → "Atiku Abubakar"
- "Kwankwaso" → "Rabiu Musa Kwankwaso"
- "Shettima" → "Kashim Shettima"
- Use full official names

Examples:
- "Compare Tinubu and Obi" → {{"candidate_a": "Bola Ahmed Tinubu", "candidate_b": "Peter Obi", "topic": null}}
- "Atiku vs Kwankwaso on education" → {{"candidate_a": "Atiku Abubakar", "candidate_b": "Rabiu Musa Kwankwaso", "topic": "education"}}
- "difference between APC and PDP on security" → {{"candidate_a": "Bola Ahmed Tinubu", "candidate_b": "Atiku Abubakar", "topic": "security"}}
- "Who is better Obi or Tinubu?" → {{"candidate_a": "Peter Obi", "candidate_b": "Bola Ahmed Tinubu", "topic": null}}"""


GENERATE_COMPARISON_PROMPT = """Create a NEUTRAL comparison. No preference, no bias.

CANDIDATE A:
Name: {name_a}
Party: {party_a}
Position: {position_a}
Promises: {promises_a}
Background: {bio_a}

CANDIDATE B:
Name: {name_b}
Party: {party_b}
Position: {position_b}
Promises: {promises_b}
Background: {bio_b}

{topic_section}

FORMAT (WhatsApp, UNDER 1500 chars):

📊 *{name_a} vs {name_b}*{topic_title}

*{name_a}* ({party_a})
• Position: [current/former role]
• Key promise: [one specific promise]
• Track record: [one factual achievement or note]

*{name_b}* ({party_b})
• Position: [current/former role]
• Key promise: [one specific promise]
• Track record: [one factual achievement or note]

⚖️ _Decide9ja is neutral. We don't endorse candidates. Vote wisely!_

STRICT RULES:
- Equal space and detail for both candidates
- NO comparative words (better, stronger, more qualified, etc.)
- Facts only, no opinions
- If data is missing, say "No data available"
- Keep under 1500 characters total"""


TOPIC_COMPARISON_PROMPT = """Create a NEUTRAL comparison focused on {topic}.

Compare their SPECIFIC positions and promises on {topic}:

CANDIDATE A ({name_a}):
Party: {party_a}
{topic} Promises: {promises_a}

CANDIDATE B ({name_b}):
Party: {party_b}
{topic} Promises: {promises_b}

FORMAT (WhatsApp):

📊 *{name_a} vs {name_b}* on {topic_title}

*{name_a}* ({party_a})
• Promise: [specific {topic} promise]
• Implementation: [if any data available]

*{name_b}* ({party_b})
• Promise: [specific {topic} promise]
• Implementation: [if any data available]

⚖️ _Decide9ja is neutral. Research both candidates before voting._

Keep under 1200 characters."""
