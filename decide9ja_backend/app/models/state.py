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
    first_name: Optional[str] = None      # User's first name (used for addressing)
    last_name: Optional[str] = None       # User's last name/surname
    name: Optional[str] = None            # Full name (computed: first_name + last_name)
    state: Optional[str] = None           # Nigerian state (primary/residence)
    lga: Optional[str] = None             # Local government area (primary/residence)

    # Enhanced Location Profile
    origin_state: Optional[str] = None    # State of origin
    origin_lga: Optional[str] = None
    residence_state: Optional[str] = None # Where user currently lives
    residence_lga: Optional[str] = None
    registered_state: Optional[str] = None  # Voter registration state
    registered_lga: Optional[str] = None
    ward: Optional[str] = None

    # Political Geography (auto-derived from LGA)
    senatorial_district: Optional[str] = None
    federal_constituency: Optional[str] = None
    state_constituency: Optional[str] = None

    # Demographics
    age_range: Optional[str] = None       # '18-24', '25-34', '35-44', '45-54', '55-64', '65+'
    gender: Optional[str] = None          # 'male', 'female', 'other', 'prefer_not_to_say'

    # Voter Status
    has_pvc: Optional[bool] = None

    # Interests & Engagement
    interests: List[str] = field(default_factory=list)  # Topics user cares about
    topics_asked: List[str] = field(default_factory=list)  # Topics queried

    # Profile Metadata
    profile_completeness: int = 0         # 0-100 score
    
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
    pending_query: Optional[str] = None   # User's first question (asked before onboarding complete)
    last_message_at: datetime = field(default_factory=datetime.utcnow)
    session_start: datetime = field(default_factory=datetime.utcnow)
    last_active_at: Optional[datetime] = None  # Last activity before this session (from DB)
    message_count: int = 0                # Total messages sent by user
    
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
            # Enhanced location profile
            "origin_state": self.origin_state,
            "origin_lga": self.origin_lga,
            "residence_state": self.residence_state,
            "residence_lga": self.residence_lga,
            "registered_state": self.registered_state,
            "registered_lga": self.registered_lga,
            "ward": self.ward,
            # Political geography
            "senatorial_district": self.senatorial_district,
            "federal_constituency": self.federal_constituency,
            "state_constituency": self.state_constituency,
            # Demographics
            "age_range": self.age_range,
            "gender": self.gender,
            "has_pvc": self.has_pvc,
            # Interests
            "interests": self.interests,
            "topics_asked": self.topics_asked,
            "profile_completeness": self.profile_completeness,
            # Flow state
            "flow": self.flow.value,
            "flow_step": self.flow_step,
            "flow_data": self.flow_data,
            "active_politician_id": self.active_politician_id,
            "active_politician_name": self.active_politician_name,
            "active_topic": self.active_topic,
            "greeted": self.greeted,
            "last_message_at": self.last_message_at.isoformat(),
            "session_start": self.session_start.isoformat(),
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "message_count": self.message_count,
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
            # Enhanced location profile
            origin_state=d.get("origin_state"),
            origin_lga=d.get("origin_lga"),
            residence_state=d.get("residence_state"),
            residence_lga=d.get("residence_lga"),
            registered_state=d.get("registered_state"),
            registered_lga=d.get("registered_lga"),
            ward=d.get("ward"),
            # Political geography
            senatorial_district=d.get("senatorial_district"),
            federal_constituency=d.get("federal_constituency"),
            state_constituency=d.get("state_constituency"),
            # Demographics
            age_range=d.get("age_range"),
            gender=d.get("gender"),
            has_pvc=d.get("has_pvc"),
            # Interests
            interests=d.get("interests", []),
            topics_asked=d.get("topics_asked", []),
            profile_completeness=d.get("profile_completeness", 0),
            # Flow state
            flow=ConversationFlow(d.get("flow", "idle")),
            flow_step=d.get("flow_step", 0),
            flow_data=d.get("flow_data", {}),
            active_politician_id=d.get("active_politician_id"),
            active_politician_name=d.get("active_politician_name"),
            active_topic=d.get("active_topic"),
            greeted=d.get("greeted", False),
            last_message_at=datetime.fromisoformat(d["last_message_at"]) if d.get("last_message_at") else datetime.utcnow(),
            session_start=datetime.fromisoformat(d["session_start"]) if d.get("session_start") else datetime.utcnow(),
            last_active_at=datetime.fromisoformat(d["last_active_at"]) if d.get("last_active_at") else None,
            message_count=d.get("message_count", 0),
            history=d.get("history", [])
        )
    
    def is_onboarding_complete(self) -> bool:
        """Check if user has completed basic onboarding."""
        # Require first_name (and optionally last_name through name), state, and lga
        return all([self.first_name, self.state, self.lga])
    
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

    def calculate_profile_completeness(self) -> int:
        """
        Calculate profile completeness score (0-100).

        Weighted scoring:
        - Basic info (name, state, lga): 30 points
        - Political geography derived: 15 points
        - Registration info: 20 points
        - Demographics: 15 points
        - Engagement (has interests): 20 points
        """
        score = 0

        # Basic info (30 points total)
        if self.name:
            score += 10
        if self.state:
            score += 10
        if self.lga:
            score += 10

        # Political geography (15 points total)
        if self.senatorial_district:
            score += 5
        if self.federal_constituency:
            score += 5
        if self.state_constituency:
            score += 5

        # Registration info (20 points total)
        if self.registered_state:
            score += 7
        if self.registered_lga:
            score += 7
        if self.has_pvc is not None:
            score += 6

        # Demographics (15 points total)
        if self.age_range:
            score += 8
        if self.gender:
            score += 7

        # Engagement - has interests (20 points)
        if self.interests and len(self.interests) >= 1:
            score += 10
        if self.interests and len(self.interests) >= 3:
            score += 10

        return min(score, 100)

    def update_profile_completeness(self):
        """Recalculate and update the profile completeness score."""
        self.profile_completeness = self.calculate_profile_completeness()

    def add_topic_asked(self, topic: str):
        """Track a topic the user has asked about."""
        if topic and topic not in self.topics_asked:
            self.topics_asked.append(topic)
            # Keep only last 50 topics
            self.topics_asked = self.topics_asked[-50:]

    def add_interest(self, interest: str):
        """Add an inferred interest (deduplicated)."""
        if interest and interest.lower() not in [i.lower() for i in self.interests]:
            self.interests.append(interest)
            # Keep only last 20 interests
            self.interests = self.interests[-20:]

    def get_engagement_tier(self) -> str:
        """Get user's engagement tier based on message count."""
        if self.message_count >= 100:
            return "power_user"
        elif self.message_count >= 50:
            return "regular"
        elif self.message_count >= 10:
            return "engaged"
        elif self.message_count >= 1:
            return "new"
        return "inactive"

    def get_profile_tier(self) -> str:
        """Get profile completion tier."""
        if self.profile_completeness >= 80:
            return "complete"
        elif self.profile_completeness >= 50:
            return "partial"
        elif self.profile_completeness >= 20:
            return "minimal"
        return "new"
