"""
Agent Registry
==============
Central registry for all agents. Handles instantiation and lookup.

Usage:
    from app.agents.registry import registry, register_agent

    @register_agent
    class MyAgent(BaseAgent):
        name = "my_agent"
        ...

    # Later
    agent = registry.get("my_agent")
    result = await agent.handle(input)
"""

from typing import Dict, Type, Optional, List
import logging

from app.agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Singleton registry for all agents.

    Features:
    - Lazy instantiation (agents created on first use)
    - Intent-based lookup
    - Statistics aggregation
    """

    _instance = None
    _agents: Dict[str, BaseAgent] = {}
    _agent_classes: Dict[str, Type[BaseAgent]] = {}
    _db_client = None
    _cache_client = None
    _llm_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._agent_classes = {}
        return cls._instance

    def configure(self, db_client=None, cache_client=None, llm_client=None):
        """Configure shared clients for all agents"""
        self._db_client = db_client
        self._cache_client = cache_client
        self._llm_client = llm_client
        logger.info("AgentRegistry configured with clients")

    def register(self, agent_class: Type[BaseAgent], **kwargs):
        """Register an agent class"""
        name = agent_class.name
        if name in self._agent_classes:
            logger.warning(f"Overwriting existing agent: {name}")
        self._agent_classes[name] = agent_class
        logger.debug(f"Registered agent class: {name}")

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent instance by name (lazy instantiation)"""
        if name not in self._agents:
            if name in self._agent_classes:
                # Instantiate on first use with configured clients
                self._agents[name] = self._agent_classes[name](
                    db_client=self._db_client,
                    cache=self._cache_client,
                    llm_client=self._llm_client
                )
                logger.info(f"Instantiated agent: {name}")
            else:
                logger.warning(f"Agent not found: {name}")
                return None
        return self._agents[name]

    def get_for_intent(self, intent: str) -> Optional[BaseAgent]:
        """Find the agent that handles a specific intent"""
        for name, agent_class in self._agent_classes.items():
            if intent in agent_class.handled_intents:
                return self.get(name)
        return None

    def get_all_for_intent(self, intent: str) -> List[BaseAgent]:
        """Find all agents that can handle a specific intent"""
        agents = []
        for name, agent_class in self._agent_classes.items():
            if intent in agent_class.handled_intents or "__all__" in agent_class.handled_intents:
                agent = self.get(name)
                if agent:
                    agents.append(agent)
        return agents

    def all_agents(self) -> Dict[str, BaseAgent]:
        """Get all registered agents (instantiates them)"""
        for name in self._agent_classes:
            if name not in self._agents:
                self.get(name)
        return self._agents.copy()

    def registered_names(self) -> List[str]:
        """Get all registered agent names"""
        return list(self._agent_classes.keys())

    def stats(self) -> Dict:
        """Get stats for all instantiated agents"""
        return {
            name: agent.stats()
            for name, agent in self._agents.items()
        }

    def reset(self):
        """Reset all agent instances (useful for testing)"""
        self._agents.clear()
        logger.info("AgentRegistry reset")

    def clear(self):
        """Clear all registered agents (useful for testing)"""
        self._agents.clear()
        self._agent_classes.clear()
        logger.info("AgentRegistry cleared")


# Global registry instance
registry = AgentRegistry()


def register_agent(agent_class: Type[BaseAgent]):
    """
    Decorator to register an agent class.

    Usage:
        @register_agent
        class MyAgent(BaseAgent):
            name = "my_agent"
            handled_intents = ["some_intent"]
            ...
    """
    registry.register(agent_class)
    return agent_class


def get_agent(name: str) -> Optional[BaseAgent]:
    """Convenience function to get an agent by name"""
    return registry.get(name)


def get_agent_for_intent(intent: str) -> Optional[BaseAgent]:
    """Convenience function to get an agent by intent"""
    return registry.get_for_intent(intent)
