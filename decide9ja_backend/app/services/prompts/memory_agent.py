"""
Memory Agent Prompt - Episodic Summarization & Extraction

Links to Source of Truth for:
- Entity definitions (for fact extraction)
- Nigerian politics knowledge (for context)

This agent handles:
- Episode summarization (consolidating conversations)
- Fact extraction (extracting user preferences, interests)
- Personalization context building
"""

from typing import Dict, List, Optional
from app.services.prompts.source_of_truth import (
    get_sot_sections,
    SOTSection,
    build_agent_prompt,
    AgentPromptConfig
)


# =============================================================================
# MEMORY-SPECIFIC TASK DEFINITIONS
# =============================================================================

EPISODE_SUMMARY_TASK = """
<task>
You are the Memory Agent for Decide9ja, specifically handling EPISODE SUMMARIZATION.

Your job is to:
1. Read a conversation session between user and Tade
2. Extract the KEY INFORMATION discussed
3. Create a concise, queryable summary
4. Identify user preferences and interests

<input>
- Conversation messages (list of user/assistant exchanges)
- User context (state, LGA, name)
</input>

<processing>
1. Identify main topics discussed
2. Note any politicians mentioned
3. Record user's concerns/interests
4. Summarize the session outcome
5. Tag with relevant keywords
</processing>
</task>
"""

EPISODE_SUMMARY_OUTPUT = """
<output_format>
Return JSON with this schema:

```json
{
  "summary": "<2-3 sentence summary of what was discussed>",
  "main_topics": ["<topic1>", "<topic2>"],
  "politicians_mentioned": ["<name1>", "<name2>"],
  "user_interests": ["<interest1>", "<interest2>"],
  "user_concerns": ["<concern1>"],
  "outcome": "<what the user learned/achieved>",
  "keywords": ["<keyword1>", "<keyword2>", "<keyword3>"],
  "sentiment": "positive|neutral|negative|mixed"
}
```

<guidelines>
- Summary should be queryable (searchable later)
- Include politician names exactly as mentioned
- Interests = topics user showed curiosity about
- Concerns = issues user expressed worry about
- Keywords should be specific and searchable
</guidelines>
</output_format>
"""

EPISODE_SUMMARY_EXAMPLES = """
<examples>

<example>
CONVERSATION:
User: Who is the governor of Lagos?
Tade: The Governor of Lagos State is *Babajide Sanwo-Olu* of the APC. He's been in office since 2019...
User: What about the tax reform, how does it affect Lagos?
Tade: Lagos stands to benefit from the new VAT sharing formula because...
User: Interesting. Thanks!

OUTPUT:
{
  "summary": "User inquired about Lagos State governor (Sanwo-Olu) and wanted to understand how the tax reform affects Lagos specifically.",
  "main_topics": ["Lagos governor", "tax reform", "VAT sharing"],
  "politicians_mentioned": ["Babajide Sanwo-Olu"],
  "user_interests": ["Lagos State politics", "tax policy", "economic impact"],
  "user_concerns": [],
  "outcome": "User learned about Lagos governor and tax reform impact on Lagos",
  "keywords": ["Lagos", "Sanwo-Olu", "APC", "tax reform", "VAT"],
  "sentiment": "positive"
}
</example>

<example>
CONVERSATION:
User: I'm worried about the new fuel prices
Tade: The fuel prices are high due to subsidy removal in June 2023...
User: Who made this decision?
Tade: President Tinubu announced the removal of fuel subsidy on May 29, 2023...
User: This is affecting everyone badly

OUTPUT:
{
  "summary": "User expressed concern about fuel prices, wanted to know who was responsible for subsidy removal. Tinubu's policy discussed.",
  "main_topics": ["fuel prices", "subsidy removal", "Tinubu policy"],
  "politicians_mentioned": ["Bola Ahmed Tinubu"],
  "user_interests": ["economic policy", "fuel subsidy"],
  "user_concerns": ["fuel prices", "cost of living", "economic hardship"],
  "outcome": "User understood Tinubu's role in subsidy removal but remains concerned",
  "keywords": ["fuel", "subsidy", "Tinubu", "prices", "economy"],
  "sentiment": "negative"
}
</example>

</examples>
"""


# =============================================================================
# FACT EXTRACTION TASK
# =============================================================================

FACT_EXTRACTION_TASK = """
<task>
You are the Memory Agent for Decide9ja, specifically handling FACT EXTRACTION.

Your job is to:
1. Read a conversation message
2. Extract any FACTS about the user
3. Identify preferences, opinions, and behavioral patterns

<fact_types>
- LOCATION: User's state, LGA, area
- PREFERENCE: What user likes/prefers
- INTEREST: Topics user cares about
- CONCERN: Issues user worries about
- OPINION: User's stance on topics (note: don't store partisan opinions)
- BEHAVIOR: How user likes to receive information (detailed, brief, Pidgin)
</fact_types>
</task>
"""

FACT_EXTRACTION_OUTPUT = """
<output_format>
Return JSON with this schema:

```json
{
  "facts": [
    {
      "type": "<LOCATION|PREFERENCE|INTEREST|CONCERN|BEHAVIOR>",
      "fact": "<the extracted fact>",
      "confidence": 0.0-1.0,
      "source_quote": "<exact quote from message>"
    }
  ],
  "no_facts_found": false
}
```

<guidelines>
- Only extract explicit facts, don't infer
- confidence: 0.9+ for explicit statements, 0.6-0.8 for implied
- source_quote should be the exact text supporting the fact
- If no facts found, return {"facts": [], "no_facts_found": true}
</guidelines>
</output_format>
"""

FACT_EXTRACTION_EXAMPLES = """
<examples>

<example>
MESSAGE: "I live in Ikeja and I'm really concerned about the roads here"

OUTPUT:
{
  "facts": [
    {
      "type": "LOCATION",
      "fact": "User lives in Ikeja",
      "confidence": 0.95,
      "source_quote": "I live in Ikeja"
    },
    {
      "type": "CONCERN",
      "fact": "User is concerned about road conditions",
      "confidence": 0.9,
      "source_quote": "really concerned about the roads here"
    }
  ],
  "no_facts_found": false
}
</example>

<example>
MESSAGE: "Can you explain in Pidgin? I understand it better"

OUTPUT:
{
  "facts": [
    {
      "type": "BEHAVIOR",
      "fact": "User prefers explanations in Pidgin",
      "confidence": 0.95,
      "source_quote": "Can you explain in Pidgin? I understand it better"
    }
  ],
  "no_facts_found": false
}
</example>

<example>
MESSAGE: "Who is the president?"

OUTPUT:
{
  "facts": [],
  "no_facts_found": true
}
</example>

<example>
MESSAGE: "I've been following the 2027 elections closely, especially the LP candidates"

OUTPUT:
{
  "facts": [
    {
      "type": "INTEREST",
      "fact": "User is interested in 2027 elections",
      "confidence": 0.9,
      "source_quote": "I've been following the 2027 elections closely"
    },
    {
      "type": "INTEREST",
      "fact": "User shows interest in Labour Party candidates",
      "confidence": 0.85,
      "source_quote": "especially the LP candidates"
    }
  ],
  "no_facts_found": false
}
</example>

</examples>
"""


# =============================================================================
# PERSONALIZATION CONTEXT TASK
# =============================================================================

PERSONALIZATION_TASK = """
<task>
You are the Memory Agent for Decide9ja, specifically handling PERSONALIZATION.

Your job is to:
1. Read the user's profile (accumulated facts)
2. Generate a personalization context for Tade to use
3. Suggest relevant topics based on user interests

<input>
- User facts (from fact extraction)
- User episodes (summarized past conversations)
- Current query (what user is asking now)
</input>

<output>
- Personalization context string for Tade's system prompt
- 2-3 sentences maximum
- Focus on relevant personalization for current query
</output>
</task>
"""


# =============================================================================
# BUILD MEMORY PROMPTS
# =============================================================================

def build_episode_summary_prompt(
    conversation: List[Dict],
    user_context: Dict = None
) -> str:
    """
    Build prompt for episode summarization.

    Args:
        conversation: List of {role: "user"|"assistant", content: "..."}
        user_context: User's state, LGA, name
    """
    config = AgentPromptConfig(
        agent_name="Memory Agent (Episode Summarizer)",
        agent_role="Conversation Summarization & Knowledge Extraction",
        sot_sections=[SOTSection.ENTITIES],
        task_specific=EPISODE_SUMMARY_TASK,
        output_format=EPISODE_SUMMARY_OUTPUT,
        examples=EPISODE_SUMMARY_EXAMPLES
    )

    base_prompt = build_agent_prompt(config)

    # Format conversation
    conv_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation
    ])

    query_section = f"""
<conversation_to_summarize>
USER CONTEXT:
- State: {user_context.get('state', 'Unknown') if user_context else 'Unknown'}
- LGA: {user_context.get('lga', 'Unknown') if user_context else 'Unknown'}

CONVERSATION:
{conv_text}
</conversation_to_summarize>

INSTRUCTIONS:
Summarize this conversation session. Return ONLY the JSON output.
"""

    return base_prompt + query_section


def build_fact_extraction_prompt(
    message: str,
    role: str = "user"
) -> str:
    """
    Build prompt for fact extraction from a single message.

    Args:
        message: The message text to extract facts from
        role: "user" or "assistant"
    """
    config = AgentPromptConfig(
        agent_name="Memory Agent (Fact Extractor)",
        agent_role="User Fact & Preference Extraction",
        sot_sections=[SOTSection.ENTITIES],
        task_specific=FACT_EXTRACTION_TASK,
        output_format=FACT_EXTRACTION_OUTPUT,
        examples=FACT_EXTRACTION_EXAMPLES
    )

    base_prompt = build_agent_prompt(config)

    query_section = f"""
<message_to_analyze>
ROLE: {role}
MESSAGE: "{message}"
</message_to_analyze>

INSTRUCTIONS:
Extract any facts about the user from this message. Return ONLY the JSON output.
If no facts can be extracted, return {{"facts": [], "no_facts_found": true}}
"""

    return base_prompt + query_section


def build_personalization_prompt(
    user_facts: List[Dict],
    user_episodes: List[Dict],
    current_query: str
) -> str:
    """
    Build prompt for generating personalization context.

    Args:
        user_facts: List of extracted facts about the user
        user_episodes: List of summarized past episodes
        current_query: What the user is asking now
    """
    config = AgentPromptConfig(
        agent_name="Memory Agent (Personalizer)",
        agent_role="Response Personalization",
        sot_sections=[SOTSection.COMMUNICATION],
        task_specific=PERSONALIZATION_TASK,
        output_format="<output>Return 2-3 sentences of personalization context.</output>",
        examples=""
    )

    base_prompt = build_agent_prompt(config)

    # Format facts
    facts_text = "\n".join([
        f"- [{f['type']}] {f['fact']}"
        for f in user_facts[:10]  # Limit to 10 most recent
    ]) if user_facts else "No facts recorded yet."

    # Format episodes
    episodes_text = "\n".join([
        f"- {ep['summary']}"
        for ep in user_episodes[:5]  # Limit to 5 most recent
    ]) if user_episodes else "No past conversations recorded."

    query_section = f"""
<personalization_context>
USER FACTS:
{facts_text}

PAST CONVERSATIONS:
{episodes_text}

CURRENT QUERY: "{current_query}"
</personalization_context>

INSTRUCTIONS:
Generate a brief personalization context (2-3 sentences) that Tade can use to
personalize the response to this user. Focus on:
1. Relevant past topics the user has asked about
2. User's communication preferences (if known)
3. User's location context (if relevant to query)

Return ONLY the personalization text, no JSON.
"""

    return base_prompt + query_section
