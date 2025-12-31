# FIX 2: CONTEXT MEMORY
# File: app/services/context_memory.py
#
# Problem: Bot forgets the active politician within the same conversation
# Example: User asks about Hon. Folorunsho, then "What has he done?" → Bot asks "which honorable?"
# Solution: Track active entities and resolve pronouns/references

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ActiveEntities:
    """Track currently active entities in conversation."""
    politician: Optional[str] = None
    politician_position: Optional[str] = None
    politician_party: Optional[str] = None
    location_state: Optional[str] = None
    location_lga: Optional[str] = None
    topic: Optional[str] = None  # e.g., "record", "policies", "election"
    last_updated: Optional[str] = None
    
    def set_politician(self, name: str, position: str = None, party: str = None):
        """Set the active politician."""
        self.politician = name
        self.politician_position = position
        self.politician_party = party
        self.last_updated = datetime.now().isoformat()
        logger.info(f"Active politician set: {name}")
    
    def set_location(self, state: str, lga: str = None):
        """Set the active location."""
        self.location_state = state
        self.location_lga = lga
        self.last_updated = datetime.now().isoformat()
        logger.info(f"Active location set: {lga}, {state}")
    
    def set_topic(self, topic: str):
        """Set the current topic."""
        self.topic = topic
        self.last_updated = datetime.now().isoformat()
    
    def clear_politician(self):
        """Clear politician context (e.g., when user changes topic)."""
        self.politician = None
        self.politician_position = None
        self.politician_party = None
        self.topic = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActiveEntities":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """User profile built through conversation."""
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    origin_state: Optional[str] = None  # Where they're from originally
    residence_state: Optional[str] = None  # Where they live now
    voted_2023: Optional[bool] = None
    will_vote_next: Optional[bool] = None
    pain_points: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    onboarding_step: int = 0
    onboarding_complete: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    intent: Optional[str] = None
    entities: Optional[dict] = None


class ConversationMemory:
    """
    Manages conversation memory for a single user.
    Tracks context, entities, and user profile.
    """
    
    def __init__(self, user_hash: str, storage_backend=None):
        self.user_hash = user_hash
        self.storage = storage_backend  # Redis, SQLite, etc.
        
        # Conversation history (last N turns)
        self.history: List[ConversationTurn] = []
        self.max_history = 10
        
        # Active entities in current conversation
        self.active = ActiveEntities()
        
        # User profile (persistent)
        self.profile = UserProfile()
        
        # Load from storage if available
        self._load()
    
    def _load(self):
        """Load memory from storage."""
        if not self.storage:
            return
        
        try:
            data = self.storage.get(f"memory:{self.user_hash}")
            if data:
                parsed = json.loads(data)
                self.active = ActiveEntities.from_dict(parsed.get("active", {}))
                self.profile = UserProfile.from_dict(parsed.get("profile", {}))
                self.history = [
                    ConversationTurn(**turn) 
                    for turn in parsed.get("history", [])
                ]
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
    
    def save(self):
        """Save memory to storage."""
        if not self.storage:
            return
        
        try:
            data = {
                "active": self.active.to_dict(),
                "profile": self.profile.to_dict(),
                "history": [asdict(turn) for turn in self.history[-self.max_history:]]
            }
            self.storage.set(f"memory:{self.user_hash}", json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def add_turn(self, role: str, content: str, intent: str = None, entities: dict = None):
        """Add a conversation turn."""
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            intent=intent,
            entities=entities
        )
        self.history.append(turn)
        
        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        self.save()
    
    def get_last_n_turns(self, n: int = 5) -> List[dict]:
        """Get last N conversation turns for context."""
        return [asdict(turn) for turn in self.history[-n:]]
    
    def resolve_reference(self, message: str) -> dict:
        """
        Resolve pronouns and references in the message.
        
        Examples:
        - "What has he done?" → resolves "he" to active politician
        - "The honorable's record" → resolves to active politician
        - "My senator" → resolves to user's state senator
        
        Returns:
            dict with resolved entities
        """
        message_lower = message.lower()
        resolved = {}
        
        # Pronoun references to active politician
        politician_pronouns = ["he", "him", "his", "she", "her", "they", "them", "their"]
        politician_references = [
            "the honorable", "the senator", "the governor", "the rep",
            "the minister", "the president", "that politician", "this politician"
        ]
        
        has_politician_ref = (
            any(f" {p} " in f" {message_lower} " or message_lower.endswith(f" {p}") for p in politician_pronouns) or
            any(ref in message_lower for ref in politician_references)
        )
        
        if has_politician_ref and self.active.politician:
            resolved["politician_name"] = self.active.politician
            resolved["politician_position"] = self.active.politician_position
            resolved["politician_party"] = self.active.politician_party
            logger.info(f"Resolved reference to: {self.active.politician}")
        
        # Location references
        location_references = ["my area", "my lga", "my state", "here", "this place"]
        if any(ref in message_lower for ref in location_references):
            if self.profile.state:
                resolved["state"] = self.profile.state
            if self.profile.lga:
                resolved["lga"] = self.profile.lga
        
        # "My senator/governor/rep" references
        if "my senator" in message_lower and self.profile.state:
            resolved["lookup_type"] = "senator"
            resolved["state"] = self.profile.state
        elif "my governor" in message_lower and self.profile.state:
            resolved["lookup_type"] = "governor"
            resolved["state"] = self.profile.state
        elif "my rep" in message_lower and self.profile.lga:
            resolved["lookup_type"] = "house_rep"
            resolved["state"] = self.profile.state
            resolved["lga"] = self.profile.lga
        
        return resolved
    
    def extract_and_update_entities(self, message: str, response: str, intent: str):
        """
        Extract entities from message/response and update active context.
        
        This should be called after generating a response to update context.
        """
        message_lower = message.lower()
        response_lower = response.lower()
        
        # If response mentions a specific politician, set them as active
        # Multiple patterns to catch various formats
        import re
        
        politician_patterns = [
            # "Governor Seyi Makinde", "Senator Kola Balogun"
            r"(?:Governor|Senator|President|Hon\.|Honorable|Rep\.|Minister)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
            # "Seyi Makinde is the Governor"
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+is\s+(?:the\s+)?(?:Governor|Senator|President|Representative)",
            # "your representative is Hon. X Y"
            r"(?:is|are)\s+(?:Hon\.|Honorable|Senator|Governor)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
            # Just "The Governor is Seyi Makinde"
            r"(?:Governor|Senator|President|Representative)\s+(?:is|of\s+\w+\s+State\s+is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
        ]
        
        name = None
        for pattern in politician_patterns:
            match = re.search(pattern, response)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if name.lower() not in ['state', 'oyo state', 'lagos state', 'nigeria', 'house of']:
                    break
                name = None
        
        if name:
            # Determine position from context
            position = None
            if "governor" in response_lower:
                position = "Governor"
            elif "senator" in response_lower:
                position = "Senator"
            elif "representative" in response_lower or "hon." in response_lower:
                position = "House Representative"
            elif "president" in response_lower:
                position = "President"
            
            # Determine party from context
            party = None
            for p in ["APC", "PDP", "LP", "NNPP", "APGA"]:
                if p in response:
                    party = p
                    break
            
            self.active.set_politician(name, position, party)
        
        # Update topic based on intent
        topic_map = {
            "politician_record": "record",
            "politician_info": "info",
            "policy_question": "policies",
            "election_info": "election",
        }
        if intent in topic_map:
            self.active.set_topic(topic_map[intent])
        
        self.save()
    
    def get_context_for_llm(self) -> str:
        """
        Build context string for LLM prompt.
        """
        context_parts = []
        
        # User profile
        if self.profile.name:
            context_parts.append(f"User's name: {self.profile.name}")
        if self.profile.state:
            location = self.profile.state
            if self.profile.lga:
                location = f"{self.profile.lga}, {self.profile.state}"
            context_parts.append(f"User's location: {location}")
        if self.profile.pain_points:
            context_parts.append(f"User's concerns: {', '.join(self.profile.pain_points)}")
        
        # Active entities
        if self.active.politician:
            politician_info = self.active.politician
            if self.active.politician_position:
                politician_info += f" ({self.active.politician_position})"
            if self.active.politician_party:
                politician_info += f" - {self.active.politician_party}"
            context_parts.append(f"Currently discussing: {politician_info}")
        
        if self.active.topic:
            context_parts.append(f"Current topic: {self.active.topic}")
        
        # Recent conversation
        if self.history:
            context_parts.append("\nRecent conversation:")
            for turn in self.history[-5:]:
                role = "User" if turn.role == "user" else "Assistant"
                # Truncate long messages
                content = turn.content[:200] + "..." if len(turn.content) > 200 else turn.content
                context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)


# === HELPER FUNCTIONS ===

def get_or_create_memory(user_hash: str, storage=None) -> ConversationMemory:
    """Get or create conversation memory for a user."""
    return ConversationMemory(user_hash, storage)


def should_use_context(intent: str) -> bool:
    """Check if this intent should use conversation context."""
    context_intents = [
        "followup",
        "politician_record",
        "politician_info",
        "policy_question",
        "confirmation",
    ]
    return intent in context_intents


# === TEST ===
if __name__ == "__main__":
    print("=== CONTEXT MEMORY TESTS ===\n")
    
    # Simulate a conversation
    memory = ConversationMemory("test_user_123")
    
    # User asks about their rep
    memory.add_turn("user", "Who is my representative for Ijebu North?", "representative_lookup")
    
    # Assistant responds with politician info
    response = "Your representative is Hon. Folorunsho Joseph Adegbesan from the APC party."
    memory.add_turn("assistant", response)
    memory.extract_and_update_entities("Who is my representative?", response, "representative_lookup")
    
    print(f"Active politician: {memory.active.politician}")
    print(f"Active party: {memory.active.politician_party}")
    
    # User asks followup
    user_msg = "What has he done?"
    resolved = memory.resolve_reference(user_msg)
    print(f"\nUser: '{user_msg}'")
    print(f"Resolved: {resolved}")
    
    # Another followup
    user_msg2 = "The honorable's achievements"
    resolved2 = memory.resolve_reference(user_msg2)
    print(f"\nUser: '{user_msg2}'")
    print(f"Resolved: {resolved2}")
    
    # Get LLM context
    print("\n=== LLM CONTEXT ===")
    print(memory.get_context_for_llm())
