"""
Conversation State Management for Decide9ja.
Tracks user flows, context, active entities, and user profiles.
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# In-memory store (use Redis in production)
_conversation_states: Dict[str, dict] = {}


def _get_default_state() -> dict:
    """Create default conversation state structure."""
    return {
        "active_flow": None,
        "flow_step": 0,
        "pending_data": {},
        "context": [],  # Last 10 messages (5 turns)
        "active_entities": {
            "politician": None,      # Currently discussing
            "location": None,        # User's location context
            "topic": None            # Current topic
        },
        "user_profile": {
            "name": None,
            "state": None,
            "lga": None,
            "senatorial_district": None,
            "voted_last_election": None,
            "will_vote_next": None,
            "pain_points": [],
            "interests": []
        },
        "last_message_at": datetime.now().isoformat(),
        "language": "en"
    }


def get_conversation_state(user_hash: str) -> dict:
    """Get current conversation state for user."""
    if user_hash not in _conversation_states:
        _conversation_states[user_hash] = _get_default_state()
    return _conversation_states[user_hash]


def update_conversation_state(user_hash: str, updates: dict):
    """Update conversation state."""
    state = get_conversation_state(user_hash)
    state.update(updates)
    state["last_message_at"] = datetime.now().isoformat()
    _conversation_states[user_hash] = state


# ===========================================
# CONTEXT MANAGEMENT
# ===========================================

def add_to_context(user_hash: str, role: str, content: str):
    """Add message to conversation context. Keep only last 10 messages."""
    state = get_conversation_state(user_hash)
    
    state["context"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only last 10 messages (5 turns)
    if len(state["context"]) > 10:
        state["context"] = state["context"][-10:]
    
    _conversation_states[user_hash] = state


def get_context(user_hash: str) -> List[dict]:
    """Get conversation context for LLM."""
    state = get_conversation_state(user_hash)
    return state.get("context", [])


def get_conversation_context_string(user_hash: str) -> str:
    """Build context string for LLM including active entities and recent conversation."""
    state = _conversation_states.get(user_hash, {})
    
    parts = []
    
    # Active politician being discussed
    politician = state.get("active_entities", {}).get("politician")
    if politician:
        parts.append(f"*Currently discussing*: {politician}")
    
    # Current topic
    topic = state.get("active_entities", {}).get("topic")
    if topic:
        parts.append(f"*Current topic*: {topic}")
    
    # User profile summary
    profile = state.get("user_profile", {})
    if profile.get("name"):
        parts.append(f"*User's name*: {profile['name']}")
    if profile.get("state"):
        location = f"{profile.get('lga', '')}, {profile['state']}" if profile.get('lga') else profile['state']
        parts.append(f"*Location*: {location}")
    if profile.get("pain_points"):
        parts.append(f"*Interests*: {', '.join(profile['pain_points'][:3])}")
    
    # Recent conversation (last 3 turns)
    context = state.get("context", [])[-6:]
    if context:
        parts.append("\n*Recent conversation*:")
        for turn in context:
            role = "User" if turn['role'] == 'user' else "Bot"
            content = turn['content'][:150] + "..." if len(turn['content']) > 150 else turn['content']
            parts.append(f"  {role}: {content}")
    
    return "\n".join(parts) if parts else "No conversation history yet."


# ===========================================
# ACTIVE ENTITY TRACKING
# ===========================================

def set_active_politician(user_hash: str, name: str):
    """Track which politician we're discussing."""
    state = get_conversation_state(user_hash)
    if "active_entities" not in state:
        state["active_entities"] = {}
    state["active_entities"]["politician"] = name
    logger.debug(f"Active politician set: {name}")


def get_active_politician(user_hash: str) -> Optional[str]:
    """Get currently discussed politician."""
    state = _conversation_states.get(user_hash, {})
    return state.get("active_entities", {}).get("politician")


def set_active_topic(user_hash: str, topic: str):
    """Track current conversation topic."""
    state = get_conversation_state(user_hash)
    if "active_entities" not in state:
        state["active_entities"] = {}
    state["active_entities"]["topic"] = topic


def get_active_topic(user_hash: str) -> Optional[str]:
    """Get current topic."""
    state = _conversation_states.get(user_hash, {})
    return state.get("active_entities", {}).get("topic")


def clear_active_entities(user_hash: str):
    """Clear active entities when topic changes significantly."""
    state = get_conversation_state(user_hash)
    state["active_entities"] = {
        "politician": None,
        "location": None,
        "topic": None
    }


def get_active_entities(user_hash: str) -> dict:
    """Get all active entities for the user."""
    state = _conversation_states.get(user_hash, {})
    return state.get("active_entities", {
        "politician": None,
        "location": None,
        "topic": None
    })


def get_full_context_for_llm(user_hash: str) -> dict:
    """
    Build complete context package for LLM call.
    Used by webhook handlers to pass full context.
    """
    return {
        "user_profile": get_user_profile(user_hash),
        "active_entities": get_active_entities(user_hash),
        "conversation_context": get_conversation_context_string(user_hash),
        "user_profile_string": get_user_profile_string(user_hash),
        "language": get_language(user_hash)
    }



# ===========================================
# USER PROFILE MANAGEMENT
# ===========================================

def update_user_profile(user_hash: str, updates: dict):
    """Update user profile."""
    state = get_conversation_state(user_hash)
    if "user_profile" not in state:
        state["user_profile"] = {}
    state["user_profile"].update(updates)
    _conversation_states[user_hash] = state


def get_user_profile(user_hash: str) -> dict:
    """Get user profile."""
    state = _conversation_states.get(user_hash, {})
    return state.get("user_profile", {})


def get_user_name(user_hash: str) -> Optional[str]:
    """Get user's name."""
    return get_user_profile(user_hash).get("name")


def get_user_state(user_hash: str) -> Optional[str]:
    """Get user's state."""
    return get_user_profile(user_hash).get("state")


def get_user_lga(user_hash: str) -> Optional[str]:
    """Get user's LGA."""
    return get_user_profile(user_hash).get("lga")


def get_user_profile_string(user_hash: str) -> str:
    """Get user profile as formatted string for LLM."""
    profile = get_user_profile(user_hash)
    
    if not profile or not profile.get("name"):
        return "User profile not yet collected."
    
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("state"):
        parts.append(f"State: {profile['state']}")
    if profile.get("lga"):
        parts.append(f"LGA: {profile['lga']}")
    if profile.get("voted_last_election") is not None:
        voted = "Yes" if profile['voted_last_election'] else "No"
        parts.append(f"Voted in 2023: {voted}")
    if profile.get("pain_points"):
        parts.append(f"Concerns: {', '.join(profile['pain_points'])}")
    
    return "\n".join(parts)


def add_pain_point(user_hash: str, pain_point: str):
    """Add a pain point/interest to user profile."""
    state = get_conversation_state(user_hash)
    if "user_profile" not in state:
        state["user_profile"] = {}
    if "pain_points" not in state["user_profile"]:
        state["user_profile"]["pain_points"] = []
    
    # Normalize and add if not duplicate
    normalized = pain_point.lower().strip()
    if normalized and normalized not in state["user_profile"]["pain_points"]:
        state["user_profile"]["pain_points"].append(normalized)


# ===========================================
# FLOW MANAGEMENT
# ===========================================

def clear_conversation_state(user_hash: str):
    """Reset conversation state completely."""
    if user_hash in _conversation_states:
        del _conversation_states[user_hash]
    logger.info(f"Cleared conversation state for {user_hash[:8]}...")


def is_flow_active(user_hash: str) -> bool:
    """Check if user is in an active flow."""
    state = get_conversation_state(user_hash)
    return state.get("active_flow") is not None


def start_flow(user_hash: str, flow_name: str, initial_data: dict = None):
    """Start a new flow for user."""
    update_conversation_state(user_hash, {
        "active_flow": flow_name,
        "flow_step": 1,
        "pending_data": initial_data or {}
    })
    logger.info(f"Started {flow_name} flow for {user_hash[:8]}...")


def advance_flow(user_hash: str, data_update: dict = None):
    """Advance flow to next step."""
    state = get_conversation_state(user_hash)
    
    new_step = state.get("flow_step", 0) + 1
    pending_data = state.get("pending_data", {})
    
    if data_update:
        pending_data.update(data_update)
    
    update_conversation_state(user_hash, {
        "flow_step": new_step,
        "pending_data": pending_data
    })


def end_flow(user_hash: str) -> dict:
    """End flow and return collected data."""
    state = get_conversation_state(user_hash)
    pending_data = state.get("pending_data", {})
    
    update_conversation_state(user_hash, {
        "active_flow": None,
        "flow_step": 0,
        "pending_data": {}
    })
    
    return pending_data


def get_flow_step(user_hash: str) -> int:
    """Get current flow step."""
    state = get_conversation_state(user_hash)
    return state.get("flow_step", 0)


def get_pending_data(user_hash: str) -> dict:
    """Get pending flow data."""
    state = get_conversation_state(user_hash)
    return state.get("pending_data", {})


# ===========================================
# LANGUAGE DETECTION
# ===========================================

def detect_language(text: str) -> str:
    """Detect language from text. Returns: en, pidgin, ha, yo, ig"""
    text_lower = text.lower()
    
    pidgin_words = ["wetin", "dey", "wahala", "oya", "abeg", "how far", "no be", "wey", "na", "sef"]
    if any(word in text_lower for word in pidgin_words):
        return "pidgin"
    
    hausa_words = ["yaya", "sannu", "lafiya", "nagode", "ina", "kai", "wannan", "yau"]
    if any(word in text_lower for word in hausa_words):
        return "ha"
    
    yoruba_words = ["bawo", "dara", "jọọ", "rara", "omo", "ekaaro", "ese"]
    if any(word in text_lower for word in yoruba_words):
        return "yo"
    
    igbo_words = ["kedu", "daalụ", "ndewo", "biko", "gini"]
    if any(word in text_lower for word in igbo_words):
        return "ig"
    
    return "en"


def set_language(user_hash: str, language: str):
    """Set user's language preference."""
    update_conversation_state(user_hash, {"language": language})


def get_language(user_hash: str) -> str:
    """Get user's language preference."""
    state = get_conversation_state(user_hash)
    return state.get("language", "en")


def is_stale_conversation(user_hash: str, timeout_minutes: int = 30) -> bool:
    """Check if conversation is stale."""
    state = _conversation_states.get(user_hash, {})
    last_msg = state.get("last_message_at")
    
    if not last_msg:
        return True
    
    try:
        last_time = datetime.fromisoformat(last_msg)
        return datetime.now() - last_time > timedelta(minutes=timeout_minutes)
    except:
        return True
