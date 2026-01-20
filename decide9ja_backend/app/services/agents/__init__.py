"""
Multi-Agent System for Decide9ja

This module implements a multi-agent architecture where each agent:
1. Has a single, focused responsibility
2. Loads ONLY its own system prompt (max ~150 lines)
3. Communicates via AgentMessage/AgentResult protocols

Architecture:
    User Message
         │
         ▼
    RouterAgent (classifies intent, dispatches)
         │
         ├──► ElectionAgent (2027 elections, polls, candidates)
         ├──► CommunityAgent (gamification, points, leaderboard)
         ├──► FactCheckAgent (claim verification)
         ├──► DigestAgent (news subscriptions)
         └──► ResponseAgent (complex queries, retrieval)

Key Design Principles:
- Each agent loads ONLY its own prompt (fixes instruction degradation)
- Agents communicate via typed protocols (AgentMessage, AgentResult)
- RouterAgent is the single entry point
- Agents can hand off to each other when needed
"""
import logging
from typing import Dict, Optional, Type

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason,
    UserContext
)

logger = logging.getLogger(__name__)

# Global agent registry
_agent_registry: Dict[str, BaseAgent] = {}


def register_agent(agent: BaseAgent) -> None:
    """Register an agent in the global registry."""
    if agent.name in _agent_registry:
        logger.warning(f"Overwriting existing agent: {agent.name}")
    _agent_registry[agent.name] = agent
    logger.info(f"Registered agent: {agent.name} with {len(agent.handled_intents)} intents")


def get_agent(name: str) -> Optional[BaseAgent]:
    """Get an agent by name from the registry."""
    return _agent_registry.get(name)


def get_all_agents() -> Dict[str, BaseAgent]:
    """Get all registered agents."""
    return _agent_registry.copy()


def clear_registry() -> None:
    """Clear all registered agents (useful for testing)."""
    _agent_registry.clear()


async def dispatch_to_agent(name: str, message: AgentMessage) -> AgentResult:
    """
    Dispatch a message to a specific agent by name.

    Handles handoffs automatically up to a maximum depth.
    """
    max_handoffs = 3
    current_agent_name = name
    current_message = message

    for i in range(max_handoffs + 1):
        agent = get_agent(current_agent_name)
        if agent is None:
            logger.error(f"Agent not found: {current_agent_name}")
            return AgentResult.failure(f"Agent not found: {current_agent_name}")

        # Update source agent in message
        current_message.source_agent = current_agent_name

        # Process with agent
        result = await agent.handle(current_message)

        # Check for handoff
        if result.handoff_to:
            if i >= max_handoffs:
                logger.warning(f"Max handoffs reached ({max_handoffs})")
                return AgentResult.failure("Max handoffs exceeded")

            logger.info(f"Handoff: {current_agent_name} -> {result.handoff_to}")
            current_agent_name = result.handoff_to
            # Preserve data from handoff
            if result.data:
                current_message.metadata.update(result.data)
            continue

        return result

    return AgentResult.failure("Dispatch loop error")


# Export all public symbols
__all__ = [
    # Base classes
    "BaseAgent",
    # Protocols
    "AgentMessage",
    "AgentResult",
    "AgentCapability",
    "HandoffReason",
    "UserContext",
    # Registry functions
    "register_agent",
    "get_agent",
    "get_all_agents",
    "clear_registry",
    "dispatch_to_agent",
]
