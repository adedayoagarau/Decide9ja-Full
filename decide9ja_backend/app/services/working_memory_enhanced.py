"""
Tade Working Memory Enhancement Module

Implements structured conversation state management with:
- Explicit state machine transitions
- Progressive profiling
- Context compression recovery
- Error recovery patterns

Integrates with existing UserState but adds structured working memory.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Callable
import json
import logging

logger = logging.getLogger(__name__)


class ConversationStage(Enum):
    """Explicit conversation stages with clear transitions"""
    GREETING = "greeting"
    LOCATION_COLLECTION = "location_collection"
    QUERY_UNDERSTANDING = "query_understanding"
    DATA_RETRIEVAL = "data_retrieval"
    RESPONSE_FORMULATION = "response_formulation"
    FOLLOW_UP = "follow_up"
    ERROR_RECOVERY = "error_recovery"
    END = "end"


class QueryType(Enum):
    """Classified query types"""
    REPRESENTATIVE = "representative"
    BUDGET = "budget"
    NEWS = "news"
    ARCHIVE = "archive"
    ELECTION = "election"
    GENERAL = "general"
    CLARIFICATION = "clarification"


@dataclass
class WorkingMemory:
    """
    Structured working memory for conversation state management.
    
    This sits alongside UserState (profile) and provides explicit
    conversation flow control with recovery mechanisms.
    """
    
    # User identification
    user_phone: str
    
    # Current conversation stage
    stage: ConversationStage = ConversationStage.GREETING
    
    # Stage history (for recovery)
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Progressive location profile
    location: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "state": None,
        "lga": None,
        "ward": None,
        "senatorial_district": None,
        "federal_constituency": None
    })
    
    # Current query context
    current_query: Dict[str, Any] = field(default_factory=lambda: {
        "type": QueryType.GENERAL,
        "query_text": "",
        "tools_used": [],
        "data_retrieved": None,
        "response_sent": False
    })
    
    # Pending actions
    pending_clarification: bool = False
    clarification_question: Optional[str] = None
    expected_answer_type: Optional[str] = None
    
    # Error recovery state
    last_error: Optional[str] = None
    retry_count: int = 0
    
    # Session metadata
    interaction_count: int = 0
    first_interaction: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # Context for compression recovery
    last_topic: Optional[str] = None
    last_representative: Optional[str] = None
    last_query_summary: Optional[str] = None
    
    def transition_to(self, new_stage: ConversationStage, reason: str = ""):
        """
        Transition to new stage with logging.
        
        Args:
            new_stage: Target stage
            reason: Why transition occurred
        """
        # Log transition
        self.stage_history.append({
            "from": self.stage.value,
            "to": new_stage.value,
            "at": datetime.utcnow().isoformat(),
            "reason": reason
        })
        
        logger.info(f"Stage transition: {self.stage.value} -> {new_stage.value} ({reason})")
        
        # Update stage
        self.stage = new_stage
        self.last_activity = datetime.utcnow()
        self.interaction_count += 1
    
    def set_location(self, state: str = None, lga: str = None, ward: str = None):
        """Update location with validation"""
        if state:
            self.location["state"] = state
        if lga:
            self.location["lga"] = lga
        if ward:
            self.location["ward"] = ward
        
        self.last_activity = datetime.utcnow()
        logger.info(f"Location updated: {state}, {lga}, {ward}")
    
    def set_query(self, query_text: str, query_type: QueryType = None):
        """Set current query with type detection"""
        self.current_query["query_text"] = query_text
        if query_type:
            self.current_query["type"] = query_type
        
        # Store for compression recovery
        self.last_query_summary = query_text[:100] if len(query_text) > 100 else query_text
        
        self.last_activity = datetime.utcnow()
    
    def add_tool_used(self, tool_name: str):
        """Track which tools were used"""
        if tool_name not in self.current_query["tools_used"]:
            self.current_query["tools_used"].append(tool_name)
    
    def set_data_retrieved(self, data: Any):
        """Store retrieved data"""
        self.current_query["data_retrieved"] = data
    
    def mark_response_sent(self):
        """Mark that response was sent"""
        self.current_query["response_sent"] = True
        self.last_activity = datetime.utcnow()
    
    def request_clarification(self, question: str, expected_type: str):
        """Set pending clarification"""
        self.pending_clarification = True
        self.clarification_question = question
        self.expected_answer_type = expected_type
        self.transition_to(ConversationStage.ERROR_RECOVERY, "clarification_needed")
    
    def resolve_clarification(self, answer: str):
        """Resolve pending clarification"""
        self.pending_clarification = False
        self.clarification_question = None
        self.expected_answer_type = None
        self.last_error = None
        self.retry_count = 0
        
        # Return to query understanding with new info
        self.transition_to(ConversationStage.QUERY_UNDERSTANDING, "clarification_resolved")
        
        return answer
    
    def record_error(self, error: str):
        """Record error for recovery"""
        self.last_error = error
        self.retry_count += 1
        logger.warning(f"Error recorded (retry #{self.retry_count}): {error}")
    
    def get_compression_recovery_context(self) -> str:
        """
        Generate context recovery message when conversation compressed.
        
        Returns string to prepend to response.
        """
        parts = []
        
        if self.last_topic:
            parts.append(f"We were discussing {self.last_topic}")
        
        if self.last_query_summary:
            parts.append(f"You asked about: {self.last_query_summary}")
        
        if self.last_representative:
            parts.append(f"Your representative is {self.last_representative}")
        
        if parts:
            return "Quick reminder — " + ". ".join(parts) + ".\n\n"
        
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "user_phone": self.user_phone,
            "stage": self.stage.value,
            "stage_history": self.stage_history,
            "location": self.location,
            "current_query": {
                **self.current_query,
                "type": self.current_query["type"].value if isinstance(self.current_query["type"], QueryType) else self.current_query["type"]
            },
            "pending_clarification": self.pending_clarification,
            "clarification_question": self.clarification_question,
            "expected_answer_type": self.expected_answer_type,
            "last_error": self.last_error,
            "retry_count": self.retry_count,
            "interaction_count": self.interaction_count,
            "first_interaction": self.first_interaction.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "last_topic": self.last_topic,
            "last_representative": self.last_representative,
            "last_query_summary": self.last_query_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemory":
        """Deserialize from dictionary"""
        memory = cls(user_phone=data["user_phone"])
        
        memory.stage = ConversationStage(data.get("stage", "greeting"))
        memory.stage_history = data.get("stage_history", [])
        memory.location = data.get("location", memory.location)
        
        query_data = data.get("current_query", {})
        memory.current_query = {
            "type": QueryType(query_data.get("type", "general")),
            "query_text": query_data.get("query_text", ""),
            "tools_used": query_data.get("tools_used", []),
            "data_retrieved": query_data.get("data_retrieved"),
            "response_sent": query_data.get("response_sent", False)
        }
        
        memory.pending_clarification = data.get("pending_clarification", False)
        memory.clarification_question = data.get("clarification_question")
        memory.expected_answer_type = data.get("expected_answer_type")
        memory.last_error = data.get("last_error")
        memory.retry_count = data.get("retry_count", 0)
        memory.interaction_count = data.get("interaction_count", 0)
        
        if "first_interaction" in data:
            memory.first_interaction = datetime.fromisoformat(data["first_interaction"])
        if "last_activity" in data:
            memory.last_activity = datetime.fromisoformat(data["last_activity"])
        
        memory.last_topic = data.get("last_topic")
        memory.last_representative = data.get("last_representative")
        memory.last_query_summary = data.get("last_query_summary")
        
        return memory


# State transition handlers
def handle_stage_transition(
    memory: WorkingMemory,
    message: str,
    intent: str,
    user_state: Any  # UserState from existing code
) -> str:
    """
    Main stage transition handler.
    
    Returns appropriate response based on current stage and input.
    """
    stage = memory.stage
    
    # Handle escape commands
    if message.lower().strip() in {"reset", "restart", "menu", "start over"}:
        memory.transition_to(ConversationStage.GREETING, "user_reset")
        return get_greeting_message(memory, user_state)
    
    # Stage-specific handlers
    handlers = {
        ConversationStage.GREETING: handle_greeting_stage,
        ConversationStage.LOCATION_COLLECTION: handle_location_stage,
        ConversationStage.QUERY_UNDERSTANDING: handle_query_stage,
        ConversationStage.DATA_RETRIEVAL: handle_retrieval_stage,
        ConversationStage.ERROR_RECOVERY: handle_error_stage,
        ConversationStage.FOLLOW_UP: handle_followup_stage
    }
    
    handler = handlers.get(stage, handle_default_stage)
    return handler(memory, message, intent, user_state)


def handle_greeting_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle greeting stage - welcome and collect location if needed"""
    
    # If returning user with location, skip to query
    if user_state.state and user_state.lga:
        memory.set_location(user_state.state, user_state.lga)
        memory.transition_to(ConversationStage.QUERY_UNDERSTANDING, "returning_user")
        return f"Welcome back! You're in {user_state.lga}, {user_state.state}. How can I help you today?"
    
    # New user or incomplete profile
    if not user_state.state:
        memory.transition_to(ConversationStage.LOCATION_COLLECTION, "new_user")
        return "Hello! I'm Tade, your civic engagement companion. To help you find your representatives, which state are you in?"
    
    # Has state but no LGA
    memory.set_location(state=user_state.state)
    memory.transition_to(ConversationStage.LOCATION_COLLECTION, "need_lga")
    return f"Got it, you're in {user_state.state}. Which Local Government Area (LGA) are you in?"


def handle_location_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle location collection with fuzzy matching"""
    
    # Try to extract location from message
    from app.services.location_matcher import identify_location  # Will create this
    
    location_result = identify_location(message, memory.location.get("state"))
    
    if location_result["success"]:
        if location_result["state"] and not memory.location["state"]:
            memory.set_location(state=location_result["state"])
            return f"Great! You're in {location_result['state']}. Which LGA?"
        
        if location_result["lga"]:
            memory.set_location(
                state=memory.location["state"] or location_result["state"],
                lga=location_result["lga"]
            )
            
            # Save to user_state for persistence
            user_state.state = memory.location["state"]
            user_state.lga = memory.location["lga"]
            
            memory.transition_to(ConversationStage.QUERY_UNDERSTANDING, "location_complete")
            return f"Perfect! I'll remember you're in {location_result['lga']}, {memory.location['state']}. What would you like to know?"
    
    # Location not understood - request clarification
    memory.request_clarification(
        question="I didn't catch that. Could you tell me which state you're in? (e.g., Lagos, Kano, Rivers)",
        expected_type="state_name"
    )
    
    return "I'm not sure I understood. Which Nigerian state are you in?"


def handle_query_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle query understanding and classification"""
    
    # Classify query type
    query_type = classify_query_type(message)
    memory.set_query(message, query_type)
    
    memory.transition_to(ConversationStage.DATA_RETRIEVAL, f"query_classified_{query_type.value}")
    
    # Return signal to trigger data retrieval (actual retrieval happens in main handler)
    return "__TRIGGER_RETRIEVAL__"


def handle_retrieval_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle after data retrieval"""
    # This stage is mostly transitional
    memory.transition_to(ConversationStage.RESPONSE_FORMULATION, "data_retrieved")
    return "__FORMULATE_RESPONSE__"


def handle_error_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle error recovery and clarification"""
    
    if memory.pending_clarification:
        # User responded to clarification
        answer = memory.resolve_clarification(message)
        return f"Thanks! Now I understand. Let me help you with that."
    
    # Generic error recovery
    memory.record_error("unhandled_error")
    
    if memory.retry_count > 2:
        # Too many retries, offer menu
        memory.transition_to(ConversationStage.GREETING, "too_many_errors")
        return "I'm having trouble understanding. Let's start fresh. What would you like to know about?\n\n1. Find my representatives\n2. Check budget information\n3. Recent political news\n4. Historical archives"
    
    return "I'm not sure I understood. Could you rephrase that?"


def handle_followup_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Handle follow-up questions"""
    
    # Check if user wants to continue or start new
    if intent in ["follow_up", "clarification"]:
        memory.transition_to(ConversationStage.QUERY_UNDERSTANDING, "follow_up")
        return "__TRIGGER_RETRIEVAL__"
    
    # New topic
    memory.transition_to(ConversationStage.QUERY_UNDERSTANDING, "new_query")
    return "__TRIGGER_RETRIEVAL__"


def handle_default_stage(memory: WorkingMemory, message: str, intent: str, user_state) -> str:
    """Default handler for unknown stages"""
    logger.warning(f"Unknown stage: {memory.stage}")
    memory.transition_to(ConversationStage.GREETING, "unknown_stage_recovery")
    return get_greeting_message(memory, user_state)


def get_greeting_message(memory: WorkingMemory, user_state) -> str:
    """Generate appropriate greeting"""
    if user_state.name:
        return f"Hello {user_state.name}! I'm Tade, your civic engagement companion. How can I help you today?"
    return "Hello! I'm Tade, your civic engagement companion. How can I help you today?"


def classify_query_type(message: str) -> QueryType:
    """Classify query type from message"""
    message_lower = message.lower()
    
    # Representative queries
    if any(word in message_lower for word in ["representative", "rep", "senator", "governor", "who is my"]):
        return QueryType.REPRESENTATIVE
    
    # Budget queries
    if any(word in message_lower for word in ["budget", "allocation", "spent", "money", "fund"]):
        return QueryType.BUDGET
    
    # News queries
    if any(word in message_lower for word in ["news", "latest", "today", "recent", "update"]):
        return QueryType.NEWS
    
    # Archive queries
    if any(word in message_lower for word in ["history", "archive", "past", "1999", "2000", "old"]):
        return QueryType.ARCHIVE
    
    # Election queries
    if any(word in message_lower for word in ["election", "vote", "pvc", "polling", "candidate"]):
        return QueryType.ELECTION
    
    return QueryType.GENERAL


# Integration helper
def integrate_with_tade():
    """
    Integration guide for adding WorkingMemory to existing Tade.
    
    Steps:
    1. Import WorkingMemory in message_handler_v4.py
    2. Load working memory alongside UserState
    3. Replace flow-based routing with stage-based routing
    4. Use handle_stage_transition() as main entry point
    5. Store working memory in Redis/SQLite alongside UserState
    """
    pass
