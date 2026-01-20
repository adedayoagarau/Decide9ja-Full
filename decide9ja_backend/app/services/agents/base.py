"""
Base Agent Class

All specialist agents inherit from BaseAgent.
Each agent:
1. Declares its capabilities and handled intents
2. Loads ONLY its own prompt (max ~150 lines)
3. Processes messages and returns results
4. Can hand off to other agents when needed
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Set
import anthropic

from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents in the multi-agent system.

    Subclasses must implement:
    - name: Unique identifier for the agent
    - capabilities: List of AgentCapability enums
    - handled_intents: Set of intent strings this agent handles
    - can_handle(): Check if agent can process a message
    - handle(): Process the message and return result
    - get_system_prompt(): Return the agent's focused prompt
    """

    # Subclasses must define these
    name: str = "base"
    capabilities: List[AgentCapability] = []
    handled_intents: Set[str] = set()

    # Claude model to use (can be overridden per agent)
    model: str = "claude-3-haiku-20240307"
    max_tokens: int = 500

    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None
        self._prompt_cache: Optional[str] = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazy-load Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        return self._client

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return this agent's focused system prompt.

        IMPORTANT: Each agent loads ONLY its own prompt.
        Do NOT import from agentic_prompts.py or source_of_truth.py.
        Keep prompts under 150 lines for optimal instruction adherence.
        """
        pass

    @abstractmethod
    async def can_handle(self, message: AgentMessage) -> bool:
        """
        Check if this agent can handle the given message.

        Default implementation checks if intent is in handled_intents.
        Override for more complex routing logic.
        """
        pass

    @abstractmethod
    async def handle(self, message: AgentMessage) -> AgentResult:
        """
        Process the message and return a result.

        This is the main entry point for agent logic.
        """
        pass

    async def call_claude(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call Claude with this agent's prompt.

        Uses the agent's focused system prompt by default.
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system_prompt or self.get_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"[{self.name}] Claude call failed: {e}")
            raise

    def handoff(
        self,
        target_agent: str,
        reason: HandoffReason = HandoffReason.CAPABILITY_REQUIRED,
        data: dict = None
    ) -> AgentResult:
        """Request handoff to another agent."""
        logger.info(f"[{self.name}] Handing off to {target_agent}: {reason.value}")
        return AgentResult.handoff(target_agent, reason, data)

    def success(self, response: str, data: dict = None) -> AgentResult:
        """Return a successful response."""
        return AgentResult.success_response(response, data)

    def failure(self, error: str, data: dict = None) -> AgentResult:
        """Return a failure response."""
        logger.error(f"[{self.name}] Failed: {error}")
        return AgentResult.failure(error, data)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} intents={len(self.handled_intents)}>"
