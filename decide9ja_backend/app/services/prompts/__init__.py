"""
Decide9ja Prompt System

Federated prompt architecture with:
- Single Source of Truth (master prompt)
- Agent-specific prompts that link to SOT

Usage:
    # Import source of truth sections
    from app.services.prompts.source_of_truth import (
        get_sot_sections,
        SOTSection,
        get_full_sot
    )

    # Import agent-specific prompt builders
    from app.services.prompts.tade_agent import (
        build_tade_system_prompt,
        build_tade_user_prompt
    )

    from app.services.prompts.understanding_agent import (
        build_understanding_prompt,
        fast_pattern_match
    )

    from app.services.prompts.memory_agent import (
        build_episode_summary_prompt,
        build_fact_extraction_prompt,
        build_personalization_prompt
    )

    from app.services.prompts.issue_agent import (
        build_issue_analysis_prompt,
        build_daily_intelligence_prompt
    )

Architecture:
    ┌─────────────────────────────────────────────┐
    │       SOURCE OF TRUTH (Master Prompt)       │
    │  - Platform identity                        │
    │  - Nigerian politics knowledge              │
    │  - Communication guidelines                 │
    │  - Guardrails                               │
    │  - Entity definitions                       │
    │  - Tool definitions                         │
    │  - Handoff protocols                        │
    │  - Current context                          │
    └─────────────────────────────────────────────┘
             ▲           ▲           ▲           ▲
             │           │           │           │
        ┌────┴───┐  ┌────┴───┐  ┌────┴───┐  ┌────┴───┐
        │ Tade   │  │Underst.│  │ Memory │  │ Issue  │
        │ Agent  │  │ Agent  │  │ Agent  │  │ Agent  │
        └────────┘  └────────┘  └────────┘  └────────┘
"""

# Source of Truth
from app.services.prompts.source_of_truth import (
    SOTSection,
    get_sot_sections,
    get_full_sot,
    get_current_context,
    build_agent_prompt,
    AgentPromptConfig,
    # Individual sections
    SOT_PLATFORM,
    SOT_POLITICS_KNOWLEDGE,
    SOT_COMMUNICATION,
    SOT_GUARDRAILS,
    SOT_ENTITIES,
    SOT_TOOLS,
    SOT_HANDOFFS,
)

# Tade Agent (Main Chatbot)
from app.services.prompts.tade_agent import (
    build_tade_system_prompt,
    build_tade_user_prompt,
)

# Understanding Agent (Intent/Entity Extraction)
from app.services.prompts.understanding_agent import (
    build_understanding_prompt,
    fast_pattern_match,
)

# Memory Agent (Episodic Memory, Fact Extraction)
from app.services.prompts.memory_agent import (
    build_episode_summary_prompt,
    build_fact_extraction_prompt,
    build_personalization_prompt,
)

# Issue Agent (News Analysis)
from app.services.prompts.issue_agent import (
    build_issue_analysis_prompt,
    build_daily_intelligence_prompt,
)

__all__ = [
    # Source of Truth
    "SOTSection",
    "get_sot_sections",
    "get_full_sot",
    "get_current_context",
    "build_agent_prompt",
    "AgentPromptConfig",
    "SOT_PLATFORM",
    "SOT_POLITICS_KNOWLEDGE",
    "SOT_COMMUNICATION",
    "SOT_GUARDRAILS",
    "SOT_ENTITIES",
    "SOT_TOOLS",
    "SOT_HANDOFFS",
    # Tade Agent
    "build_tade_system_prompt",
    "build_tade_user_prompt",
    # Understanding Agent
    "build_understanding_prompt",
    "fast_pattern_match",
    # Memory Agent
    "build_episode_summary_prompt",
    "build_fact_extraction_prompt",
    "build_personalization_prompt",
    # Issue Agent
    "build_issue_analysis_prompt",
    "build_daily_intelligence_prompt",
]
