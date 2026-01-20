"""
Agent Communication Protocols

Defines the message types and results used for inter-agent communication.
This is the contract between agents - keep it minimal and stable.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from enum import Enum


class AgentCapability(Enum):
    """Capabilities that agents can declare."""
    ROUTING = "routing"
    ELECTION_2027 = "election_2027"
    COMMUNITY = "community"
    FACT_CHECK = "fact_check"
    DIGEST = "digest"
    FLOW_MANAGEMENT = "flow_management"
    RESPONSE_GENERATION = "response_generation"
    RETRIEVAL = "retrieval"


class HandoffReason(Enum):
    """Reasons for handing off to another agent."""
    INTENT_MISMATCH = "intent_mismatch"
    CAPABILITY_REQUIRED = "capability_required"
    ESCALATION = "escalation"
    FALLBACK = "fallback"
    COMPLETION = "completion"


@dataclass
class UserContext:
    """User context passed to agents."""
    phone: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    active_topic: Optional[str] = None
    active_politician_id: Optional[str] = None
    active_politician_name: Optional[str] = None
    flow_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_user_state(cls, user_state) -> "UserContext":
        """Create UserContext from UserState object."""
        return cls(
            phone=user_state.phone,
            name=user_state.name,
            first_name=getattr(user_state, 'first_name', None),
            state=user_state.state,
            lga=user_state.lga,
            active_topic=getattr(user_state, 'active_topic', None),
            active_politician_id=getattr(user_state, 'active_politician_id', None),
            active_politician_name=getattr(user_state, 'active_politician_name', None),
            flow_data=getattr(user_state, 'flow_data', {}) or {}
        )


@dataclass
class AgentMessage:
    """
    Message passed between agents.

    This is the primary communication unit in the multi-agent system.
    RouterAgent creates this after intent classification and passes
    it to specialist agents.
    """
    query: str
    user_context: UserContext
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    retrieval_context: Optional[Dict[str, Any]] = None
    source_agent: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_intent(self, intent: str, entities: Dict[str, Any] = None,
                    confidence: float = 0.0) -> "AgentMessage":
        """Return a new message with updated intent information."""
        return AgentMessage(
            query=self.query,
            user_context=self.user_context,
            intent=intent,
            entities=entities or self.entities,
            retrieval_context=self.retrieval_context,
            source_agent=self.source_agent,
            confidence=confidence,
            metadata=self.metadata
        )


@dataclass
class AgentResult:
    """
    Result returned by an agent after processing.

    Agents return this to indicate success/failure and optionally
    request handoff to another agent.
    """
    success: bool
    response: Optional[str] = None
    handoff_to: Optional[str] = None
    handoff_reason: Optional[HandoffReason] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0

    @classmethod
    def success_response(cls, response: str, data: Dict[str, Any] = None) -> "AgentResult":
        """Create a successful response."""
        return cls(success=True, response=response, data=data or {})

    @classmethod
    def handoff(cls, target_agent: str, reason: HandoffReason,
                data: Dict[str, Any] = None) -> "AgentResult":
        """Create a handoff request to another agent."""
        return cls(
            success=True,
            handoff_to=target_agent,
            handoff_reason=reason,
            data=data or {}
        )

    @classmethod
    def failure(cls, error: str, data: Dict[str, Any] = None) -> "AgentResult":
        """Create a failure response."""
        return cls(success=False, error=error, data=data or {})
