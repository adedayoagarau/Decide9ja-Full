"""
Decide9ja Multi-Agent System
============================

Architecture: Database First, LLM Last
- Gatekeeper → Classifier → Router → Specialist → Response

Cost Target: 80% of queries at $0 (database + cache + rules)
"""

from app.agents.base import (
    # Enums
    AgentTier,
    CostLevel,
    # Data classes
    UserContext,
    AgentInput,
    AgentOutput,
    # Base classes
    BaseAgent,
    DatabaseAgent,
    LLMAgent,
)

from app.agents.registry import (
    registry,
    register_agent,
    get_agent,
    get_agent_for_intent,
    AgentRegistry,
)

__all__ = [
    # Enums
    "AgentTier",
    "CostLevel",
    # Data classes
    "UserContext",
    "AgentInput",
    "AgentOutput",
    # Base classes
    "BaseAgent",
    "DatabaseAgent",
    "LLMAgent",
    # Registry
    "registry",
    "register_agent",
    "get_agent",
    "get_agent_for_intent",
    "AgentRegistry",
]
