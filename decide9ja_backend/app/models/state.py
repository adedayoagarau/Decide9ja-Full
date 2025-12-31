"""
User state management for conversation flows.
Implements the conversation state machine per the Master Fix Specification.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import json


class ConversationFlow(Enum):
    """Conversation state machine states."""
    IDLE = "idle"                    # Default state, ready for any query
    ONBOARDING = "onboarding"        # Collecting user profile
    ISSUE_FLOW = "issue_flow"        # Reporting community issue
    AWAITING_CLARIFY = "clarify"     # Need specific info to proceed
    CONFIRMING = "confirming"        # Awaiting yes/no confirmation


@dataclass
class UserState:
    """
    Complete user state for conversation management.
    
    Stored in:
    - Redis: Session data (flow, context, history) with 30min TTL
    - PostgreSQL: Profile data (name, state, lga) for persistence
    """
    # Identity
    user_id: str                          # Hashed phone number
    phone: str                            # For sending responses
    
    # Profile (persisted to PostgreSQL)
    name: Optional[str] = None
    state: Optional[str] = None           # Nigerian state
    lga: Optional[str] = None             # Local government area
    
    # Flow State (stored in Redis, TTL 30 min)
    flow: ConversationFlow = ConversationFlow.IDLE
    flow_step: int = 0
    flow_data: dict = field(default_factory=dict)  # Temporary data for current flow
    
    # Context (stored in Redis, TTL 10 min)
    active_politician_id: Optional[str] = None
    active_politician_name: Optional[str] = None
    active_topic: Optional[str] = None
    
    # Session metadata
    greeted: bool = False                 # Has Tade introduced himself this session?
    last_message_at: datetime = field(default_factory=datetime.utcnow)
    session_start: datetime = field(default_factory=datetime.utcnow)
    
    # Conversation History (last 6 turns for LLM context)
    history: List[dict] = field(default_factory=list)
    
    def to_redis(self) -> str:
        """Serialize for Redis storage."""
        return json.dumps({
            "user_id": self.user_id,
            "phone": self.phone,
            "name": self.name,
            "state": self.state,
            "lga": self.lga,
            "flow": self.flow.value,
            "flow_step": self.flow_step,
            "flow_data": self.flow_data,
            "active_politician_id": self.active_politician_id,
            "active_politician_name": self.active_politician_name,
            "active_topic": self.active_topic,
            "greeted": self.greeted,
            "last_message_at": self.last_message_at.isoformat(),
            "session_start": self.session_start.isoformat(),
            "history": self.history[-6:]  # Keep last 6 turns only
        })
    
    @classmethod
    def from_redis(cls, data: str, phone: str) -> "UserState":
        """Deserialize from Redis."""
        d = json.loads(data)
        return cls(
            user_id=d["user_id"],
            phone=phone,
            name=d.get("name"),
            state=d.get("state"),
            lga=d.get("lga"),
            flow=ConversationFlow(d.get("flow", "idle")),
            flow_step=d.get("flow_step", 0),
            flow_data=d.get("flow_data", {}),
            active_politician_id=d.get("active_politician_id"),
            active_politician_name=d.get("active_politician_name"),
            active_topic=d.get("active_topic"),
            greeted=d.get("greeted", False),
            last_message_at=datetime.fromisoformat(d["last_message_at"]) if d.get("last_message_at") else datetime.utcnow(),
            session_start=datetime.fromisoformat(d["session_start"]) if d.get("session_start") else datetime.utcnow(),
            history=d.get("history", [])
        )
    
    def is_onboarding_complete(self) -> bool:
        """Check if user has completed basic onboarding."""
        return all([self.name, self.state, self.lga])
    
    def is_flow_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if current flow has timed out."""
        if self.flow == ConversationFlow.IDLE:
            return False
        elapsed = (datetime.utcnow() - self.last_message_at).total_seconds() / 60
        return elapsed > timeout_minutes
    
    def is_context_expired(self, timeout_minutes: int = 10) -> bool:
        """Check if active context (politician, topic) has expired."""
        elapsed = (datetime.utcnow() - self.last_message_at).total_seconds() / 60
        return elapsed > timeout_minutes
    
    def clear_flow(self):
        """Reset to IDLE state."""
        self.flow = ConversationFlow.IDLE
        self.flow_step = 0
        self.flow_data = {}
    
    def clear_context(self):
        """Clear active politician/topic context."""
        self.active_politician_id = None
        self.active_politician_name = None
        self.active_topic = None
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history."""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep only last 6 turns
        self.history = self.history[-6:]
    
    def get_history_for_llm(self) -> List[dict]:
        """Get conversation history formatted for LLM context."""
        return [{"role": h["role"], "content": h["content"]} for h in self.history]
