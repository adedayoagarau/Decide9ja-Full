"""
Working Memory Module for Decide9ja
====================================
Enhanced conversation state management extracted from VoltAgent Tade patterns.

This module provides:
- Structured working memory schema with validation
- Conversation state machine with substates
- Context compression and recovery
- State persistence utilities

Usage:
    from enhancements.working_memory import WorkingMemory, ConversationState
    
    # Create working memory for user
    memory = WorkingMemory(user_id="user_hash")
    memory.update_state("awaiting_location", {"question": "Which state?"})
    
    # Recover context after interruption
    if memory.is_stale():
        memory.compress_context()
        recovery_prompt = memory.get_recovery_prompt()
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional, Dict, List, Any, Callable
import json
import logging

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """
    Conversation state machine states.
    Extracted from VoltAgent Tade and adapted for Decide9ja.
    """
    IDLE = "idle"                           # Ready for any query
    AWAITING_LOCATION = "awaiting_location" # Waiting for user location
    AWAITING_CLARIFICATION = "awaiting_clarification"  # Need more info
    IN_TOOL_FLOW = "in_tool_flow"           # Multi-step tool interaction
    CONFIRMING = "confirming"               # Yes/no confirmation needed
    PROCESSING = "processing"               # Async operation in progress
    RECOVERING = "recovering"               # Error recovery mode


class SubState(Enum):
    """Sub-states for granular flow tracking."""
    NONE = "none"
    # Location flow
    ASKING_STATE = "asking_state"
    ASKING_LGA = "asking_lga"
    CONFIRMING_LOCATION = "confirming_location"
    # Tool flows
    FETCHING_REPRESENTATIVES = "fetching_reps"
    QUERYING_BUDGET = "querying_budget"
    SEARCHING_ARCHIVES = "searching_archives"
    GETTING_NEWS = "getting_news"
    # Error states
    TOOL_FAILED = "tool_failed"
    INVALID_INPUT = "invalid_input"
    TIMEOUT = "timeout"


@dataclass
class TurnMemory:
    """Single conversation turn with metadata."""
    role: str  # "user" | "assistant" | "tool"
    content: str
    timestamp: datetime
    intent: Optional[str] = None
    state_at_turn: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextData:
    """Structured context data that can be compressed/recovered."""
    active_politician: Optional[Dict[str, Any]] = None
    active_topic: Optional[str] = None
    location_context: Optional[Dict[str, str]] = None
    pending_query: Optional[str] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContextData":
        return cls(**data)


@dataclass
class WorkingMemory:
    """
    Enhanced working memory for conversation management.
    
    Provides structured state tracking, context management,
    and recovery capabilities for Decide9ja.
    """
    
    # Identity
    user_id: str
    
    # Current state
    state: ConversationState = field(default=ConversationState.IDLE)
    sub_state: SubState = field(default=SubState.NONE)
    
    # State data
    state_data: Dict[str, Any] = field(default_factory=dict)
    
    # Conversation context
    context: ContextData = field(default_factory=ContextData)
    
    # Conversation history (working memory - recent only)
    turns: List[TurnMemory] = field(default_factory=list)
    max_turns: int = 10
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    state_entered_at: datetime = field(default_factory=datetime.utcnow)
    
    # Configuration
    state_timeout_minutes: Dict[ConversationState, int] = field(default_factory=lambda: {
        ConversationState.IDLE: 30,
        ConversationState.AWAITING_LOCATION: 15,
        ConversationState.AWAITING_CLARIFICATION: 20,
        ConversationState.IN_TOOL_FLOW: 25,
        ConversationState.CONFIRMING: 10,
        ConversationState.PROCESSING: 5,
        ConversationState.RECOVERING: 10,
    })
    
    # Recovery tracking
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    compressed_context: Optional[str] = None
    
    def update_state(
        self, 
        new_state: ConversationState | str,
        data: Optional[Dict[str, Any]] = None,
        sub_state: Optional[SubState | str] = None
    ) -> "WorkingMemory":
        """
        Update the conversation state with optional data.
        
        Args:
            new_state: The new state to transition to
            data: Optional data associated with this state
            sub_state: Optional sub-state for granular tracking
        """
        # Convert string to enum if needed
        if isinstance(new_state, str):
            new_state = ConversationState(new_state)
        if isinstance(sub_state, str):
            sub_state = SubState(sub_state)
            
        old_state = self.state
        self.state = new_state
        self.state_entered_at = datetime.utcnow()
        
        if sub_state:
            self.sub_state = sub_state
            
        if data:
            self.state_data = {**self.state_data, **data}
            
        self.last_update = datetime.utcnow()
        
        logger.debug(f"State transition: {old_state.value} -> {new_state.value}")
        return self
    
    def add_turn(
        self, 
        role: str, 
        content: str,
        intent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> "WorkingMemory":
        """Add a conversation turn to working memory."""
        turn = TurnMemory(
            role=role,
            content=content[:500],  # Truncate long content
            timestamp=datetime.utcnow(),
            intent=intent,
            state_at_turn=self.state.value,
            metadata=metadata or {}
        )
        self.turns.append(turn)
        
        # Keep only recent turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
            
        self.last_update = datetime.utcnow()
        return self
    
    def is_stale(self) -> bool:
        """Check if current state has timed out."""
        timeout = self.state_timeout_minutes.get(self.state, 30)
        elapsed = (datetime.utcnow() - self.state_entered_at).total_seconds() / 60
        return elapsed > timeout
    
    def get_time_in_state(self) -> timedelta:
        """Get time spent in current state."""
        return datetime.utcnow() - self.state_entered_at
    
    def compress_context(self) -> str:
        """
        Compress context for recovery after interruption.
        
        Returns a summary string that captures essential context.
        """
        parts = []
        
        # State info
        parts.append(f"State: {self.state.value}")
        if self.sub_state != SubState.NONE:
            parts.append(f"Sub-state: {self.sub_state.value}")
        
        # Context summary
        if self.context.active_politician:
            parts.append(f"Discussing: {self.context.active_politician.get('name', 'Unknown')}")
        if self.context.active_topic:
            parts.append(f"Topic: {self.context.active_topic}")
        if self.context.location_context:
            loc = self.context.location_context
            parts.append(f"Location: {loc.get('lga', '')}, {loc.get('state', '')}")
        if self.context.pending_query:
            parts.append(f"Pending: {self.context.pending_query}")
        
        # Recent turns summary
        if self.turns:
            recent_user_turns = [t for t in self.turns if t.role == "user"][-2:]
            if recent_user_turns:
                parts.append(f"Last asked: {recent_user_turns[-1].content[:50]}...")
        
        # State data keys (not values for privacy)
        if self.state_data:
            parts.append(f"Data keys: {', '.join(self.state_data.keys())}")
        
        self.compressed_context = " | ".join(parts)
        return self.compressed_context
    
    def get_recovery_prompt(self) -> str:
        """
        Generate a recovery prompt after interruption.
        
        This helps users pick up where they left off.
        """
        if self.recovery_attempts >= self.max_recovery_attempts:
            # Too many recovery attempts, reset to idle
            self.reset()
            return "How can I help you today?"
        
        self.recovery_attempts += 1
        
        # Generate context-appropriate recovery
        if self.state == ConversationState.AWAITING_LOCATION:
            question = self.state_data.get("question", "Where are you located?")
            return f"We were talking about your location. {question}"
        
        elif self.state == ConversationState.IN_TOOL_FLOW:
            flow_name = self.state_data.get("flow_name", "that request")
            return f"I was still working on {flow_name}. Would you like me to continue?"
        
        elif self.state == ConversationState.CONFIRMING:
            action = self.state_data.get("action_description", "this")
            return f"Before the break, I asked if you wanted to {action}. Still interested?"
        
        elif self.context.pending_query:
            return f"You asked about '{self.context.pending_query}'. I'm still looking into that."
        
        elif self.context.active_topic:
            return f"We were discussing {self.context.active_topic}. What would you like to know?"
        
        return "Welcome back! How can I help you today?"
    
    def reset(self, clear_context: bool = True) -> "WorkingMemory":
        """Reset to idle state."""
        self.state = ConversationState.IDLE
        self.sub_state = SubState.NONE
        self.state_data = {}
        self.recovery_attempts = 0
        
        if clear_context:
            self.context = ContextData()
            self.turns = []
        
        self.last_update = datetime.utcnow()
        return self
    
    def update_context(
        self, 
        politician: Optional[Dict] = None,
        topic: Optional[str] = None,
        location: Optional[Dict[str, str]] = None,
        pending_query: Optional[str] = None
    ) -> "WorkingMemory":
        """Update context data."""
        if politician:
            self.context.active_politician = politician
        if topic:
            self.context.active_topic = topic
        if location:
            self.context.location_context = location
        if pending_query:
            self.context.pending_query = pending_query
            
        self.last_update = datetime.utcnow()
        return self
    
    def add_tool_result(self, tool_name: str, result: Any, success: bool = True) -> "WorkingMemory":
        """Record a tool execution result."""
        self.context.tool_results.append({
            "tool": tool_name,
            "result": result,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep only recent results
        if len(self.context.tool_results) > 5:
            self.context.tool_results = self.context.tool_results[-5:]
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "state": self.state.value,
            "sub_state": self.sub_state.value,
            "state_data": self.state_data,
            "context": self.context.to_dict(),
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "timestamp": t.timestamp.isoformat(),
                    "intent": t.intent,
                    "state_at_turn": t.state_at_turn,
                    "metadata": t.metadata
                }
                for t in self.turns
            ],
            "created_at": self.created_at.isoformat(),
            "last_update": self.last_update.isoformat(),
            "state_entered_at": self.state_entered_at.isoformat(),
            "recovery_attempts": self.recovery_attempts,
            "compressed_context": self.compressed_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemory":
        """Deserialize from dictionary."""
        memory = cls(
            user_id=data["user_id"],
            state=ConversationState(data.get("state", "idle")),
            sub_state=SubState(data.get("sub_state", "none")),
            state_data=data.get("state_data", {}),
            context=ContextData.from_dict(data.get("context", {})),
            recovery_attempts=data.get("recovery_attempts", 0),
            compressed_context=data.get("compressed_context")
        )
        
        # Parse turns
        for turn_data in data.get("turns", []):
            turn = TurnMemory(
                role=turn_data["role"],
                content=turn_data["content"],
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                intent=turn_data.get("intent"),
                state_at_turn=turn_data.get("state_at_turn"),
                metadata=turn_data.get("metadata", {})
            )
            memory.turns.append(turn)
        
        # Parse timestamps
        if "created_at" in data:
            memory.created_at = datetime.fromisoformat(data["created_at"])
        if "last_update" in data:
            memory.last_update = datetime.fromisoformat(data["last_update"])
        if "state_entered_at" in data:
            memory.state_entered_at = datetime.fromisoformat(data["state_entered_at"])
            
        return memory
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "WorkingMemory":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class WorkingMemoryManager:
    """
    Manager for working memory instances.
    Handles persistence and retrieval.
    """
    
    def __init__(self, redis_client=None, db_session_factory=None):
        self._cache: Dict[str, WorkingMemory] = {}
        self.redis = redis_client
        self.db_factory = db_session_factory
        self.ttl_seconds = 1800  # 30 minutes
    
    def get(self, user_id: str) -> WorkingMemory:
        """Get or create working memory for user."""
        # Check in-memory cache
        if user_id in self._cache:
            memory = self._cache[user_id]
            # Check if stale
            if memory.is_stale() and memory.state != ConversationState.IDLE:
                logger.info(f"Working memory stale for {user_id}, compressing context")
                memory.compress_context()
            return memory
        
        # Try Redis
        if self.redis:
            try:
                data = self.redis.get(f"working_memory:{user_id}")
                if data:
                    memory = WorkingMemory.from_json(data)
                    self._cache[user_id] = memory
                    return memory
            except Exception as e:
                logger.error(f"Redis error loading working memory: {e}")
        
        # Create new
        memory = WorkingMemory(user_id=user_id)
        self._cache[user_id] = memory
        return memory
    
    def save(self, memory: WorkingMemory) -> bool:
        """Save working memory to persistence."""
        self._cache[memory.user_id] = memory
        
        if self.redis:
            try:
                self.redis.setex(
                    f"working_memory:{memory.user_id}",
                    self.ttl_seconds,
                    memory.to_json()
                )
                return True
            except Exception as e:
                logger.error(f"Redis error saving working memory: {e}")
        
        return True  # In-memory only is fine
    
    def clear(self, user_id: str) -> None:
        """Clear working memory for user."""
        if user_id in self._cache:
            del self._cache[user_id]
        
        if self.redis:
            try:
                self.redis.delete(f"working_memory:{user_id}")
            except Exception as e:
                logger.error(f"Redis error clearing working memory: {e}")


# Singleton instance (for convenience)
_working_memory_manager: Optional[WorkingMemoryManager] = None


def get_working_memory_manager(
    redis_client=None, 
    db_session_factory=None
) -> WorkingMemoryManager:
    """Get or create the global working memory manager."""
    global _working_memory_manager
    if _working_memory_manager is None:
        _working_memory_manager = WorkingMemoryManager(redis_client, db_session_factory)
    return _working_memory_manager


def get_working_memory(user_id: str) -> WorkingMemory:
    """Convenience function to get working memory for a user."""
    return get_working_memory_manager().get(user_id)


def save_working_memory(memory: WorkingMemory) -> bool:
    """Convenience function to save working memory."""
    return get_working_memory_manager().save(memory)