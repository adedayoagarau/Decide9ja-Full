"""
Conversation Context Manager
============================
Persistent conversation memory across all modalities.

Features:
- Cross-modal context (text, voice, image, location)
- Hot storage (Redis) for active conversations
- Cold storage (DB) for long-term memory
- Automatic summarization of old history
- Entity accumulation across conversation

Usage:
    from app.memory import context_manager

    # Get or create context
    ctx = await context_manager.get_context(user_id)

    # Add entry
    await context_manager.add_entry(user_id, ModalityEntry(...))

    # Get formatted context for LLM
    prompt_ctx = await context_manager.get_context_for_prompt(user_id)
"""

import json
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

class Modality(str, Enum):
    """Supported input/output modalities"""
    TEXT = "text"
    VOICE_NOTE = "voice_note"
    VOICE_CALL = "voice_call"
    IMAGE = "image"
    LOCATION = "location"
    DOCUMENT = "document"
    VIDEO = "video"


class Role(str, Enum):
    """Conversation participant roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ModalityEntry:
    """Single entry in conversation history"""
    id: str
    timestamp: datetime
    modality: str  # Modality enum value
    role: str  # Role enum value

    # Content (varies by modality)
    text: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    image_analysis: Optional[Dict] = None
    location: Optional[Dict] = None  # {lat, lng, address, lga, state}
    document_url: Optional[str] = None
    video_url: Optional[str] = None

    # Metadata
    language: Optional[str] = None
    sentiment: Optional[str] = None
    intent: Optional[str] = None
    confidence: Optional[float] = None
    entities: List[Dict] = field(default_factory=list)

    # Processing info
    processing_time_ms: Optional[float] = None
    cost_level: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ModalityEntry":
        """Create from dictionary"""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def format_for_prompt(self) -> str:
        """Format entry for LLM prompt"""
        prefix = f"[{self.role}]"

        if self.modality == Modality.IMAGE.value and self.image_analysis:
            desc = self.image_analysis.get("description", "image")
            return f"{prefix} [Sent image: {desc}]"

        if self.modality == Modality.LOCATION.value and self.location:
            addr = self.location.get("address", "unknown location")
            return f"{prefix} [Shared location: {addr}]"

        if self.modality in [Modality.VOICE_NOTE.value, Modality.VOICE_CALL.value]:
            return f"{prefix} [via voice]: {self.text or ''}"

        return f"{prefix}: {self.text or ''}"


@dataclass
class UserProfile:
    """Persistent user profile"""
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    preferred_language: str = "en"
    notification_preferences: Dict = field(default_factory=dict)
    followed_politicians: List[str] = field(default_factory=list)
    followed_topics: List[str] = field(default_factory=list)
    civic_score: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(**data) if data else cls()


@dataclass
class ConversationContext:
    """Full conversation state for a user"""
    user_id: str
    phone_hash: str
    created_at: datetime
    updated_at: datetime

    # User profile (persists forever)
    user_profile: UserProfile = field(default_factory=UserProfile)

    # Conversation history (last N turns, then summarized)
    history: List[ModalityEntry] = field(default_factory=list)
    history_summary: Optional[str] = None  # Summary of older conversation

    # Active session state
    session_id: Optional[str] = None
    session_start: Optional[datetime] = None
    current_intent: Optional[str] = None
    current_flow: Optional[str] = None  # e.g., "issue_reporting_step_2"
    flow_data: Dict = field(default_factory=dict)  # Data for multi-step flows
    pending_questions: List[str] = field(default_factory=list)

    # Extracted entities (accumulated across conversation)
    mentioned_politicians: List[str] = field(default_factory=list)
    mentioned_locations: List[Dict] = field(default_factory=list)
    mentioned_issues: List[Dict] = field(default_factory=list)
    uploaded_media: List[Dict] = field(default_factory=list)

    # Voice call state
    in_active_call: bool = False
    call_sid: Optional[str] = None
    call_start_time: Optional[datetime] = None

    # Stats
    total_messages: int = 0
    voice_messages: int = 0
    image_messages: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        data = {
            "user_id": self.user_id,
            "phone_hash": self.phone_hash,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user_profile": self.user_profile.to_dict(),
            "history": [e.to_dict() for e in self.history],
            "history_summary": self.history_summary,
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "current_intent": self.current_intent,
            "current_flow": self.current_flow,
            "flow_data": self.flow_data,
            "pending_questions": self.pending_questions,
            "mentioned_politicians": self.mentioned_politicians,
            "mentioned_locations": self.mentioned_locations,
            "mentioned_issues": self.mentioned_issues,
            "uploaded_media": self.uploaded_media,
            "in_active_call": self.in_active_call,
            "call_sid": self.call_sid,
            "call_start_time": self.call_start_time.isoformat() if self.call_start_time else None,
            "total_messages": self.total_messages,
            "voice_messages": self.voice_messages,
            "image_messages": self.image_messages,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            phone_hash=data["phone_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            user_profile=UserProfile.from_dict(data.get("user_profile", {})),
            history=[ModalityEntry.from_dict(e) for e in data.get("history", [])],
            history_summary=data.get("history_summary"),
            session_id=data.get("session_id"),
            session_start=datetime.fromisoformat(data["session_start"]) if data.get("session_start") else None,
            current_intent=data.get("current_intent"),
            current_flow=data.get("current_flow"),
            flow_data=data.get("flow_data", {}),
            pending_questions=data.get("pending_questions", []),
            mentioned_politicians=data.get("mentioned_politicians", []),
            mentioned_locations=data.get("mentioned_locations", []),
            mentioned_issues=data.get("mentioned_issues", []),
            uploaded_media=data.get("uploaded_media", []),
            in_active_call=data.get("in_active_call", False),
            call_sid=data.get("call_sid"),
            call_start_time=datetime.fromisoformat(data["call_start_time"]) if data.get("call_start_time") else None,
            total_messages=data.get("total_messages", 0),
            voice_messages=data.get("voice_messages", 0),
            image_messages=data.get("image_messages", 0),
        )


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

class ContextManager:
    """
    Manages conversation context across all modalities.

    Storage strategy:
    - Hot: Redis with 24-hour TTL for active conversations
    - Cold: PostgreSQL for long-term storage
    """

    # Configuration
    MAX_HISTORY_ENTRIES = 50
    SUMMARIZE_THRESHOLD = 40
    CONTEXT_TTL_HOURS = 24
    SESSION_TIMEOUT_MINUTES = 30

    def __init__(self, redis_client=None, db_client=None, llm_client=None):
        self.redis = redis_client
        self.db = db_client
        self.llm = llm_client  # For summarization
        self._local_cache: Dict[str, ConversationContext] = {}  # Fallback if no Redis

    def configure(self, redis_client=None, db_client=None, llm_client=None):
        """Configure storage backends"""
        if redis_client:
            self.redis = redis_client
        if db_client:
            self.db = db_client
        if llm_client:
            self.llm = llm_client

    async def get_context(self, user_id: str) -> ConversationContext:
        """Load or create conversation context"""

        # Try hot storage (Redis) first
        cached = await self._get_from_cache(user_id)
        if cached:
            # Check if session expired
            if self._is_session_expired(cached):
                await self._start_new_session(cached)
            return cached

        # Try cold storage (DB)
        stored = await self._get_from_db(user_id)
        if stored:
            await self._start_new_session(stored)
            await self._warm_cache(stored)
            return stored

        # New user - create fresh context
        context = ConversationContext(
            user_id=user_id,
            phone_hash=self._hash(user_id),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            session_id=self._generate_session_id(),
            session_start=datetime.utcnow(),
        )

        await self._save_context(context)
        logger.info(f"Created new context for user {user_id[:8]}...")

        return context

    async def add_entry(
        self,
        user_id: str,
        entry: ModalityEntry,
        extract_entities: bool = True
    ) -> ConversationContext:
        """Add new entry to conversation history"""
        context = await self.get_context(user_id)

        # Add to history
        context.history.append(entry)
        context.total_messages += 1

        # Track modality stats
        if entry.modality in [Modality.VOICE_NOTE.value, Modality.VOICE_CALL.value]:
            context.voice_messages += 1
        elif entry.modality == Modality.IMAGE.value:
            context.image_messages += 1

        # Extract and accumulate entities
        if extract_entities and entry.entities:
            for entity in entry.entities:
                entity_type = entity.get("type", "")
                entity_value = entity.get("value", "")

                if entity_type == "politician" and entity_value:
                    if entity_value not in context.mentioned_politicians:
                        context.mentioned_politicians.append(entity_value)
                        # Keep last 20
                        context.mentioned_politicians = context.mentioned_politicians[-20:]

                elif entity_type == "location" and entity_value:
                    context.mentioned_locations.append({
                        "value": entity_value,
                        "timestamp": entry.timestamp.isoformat()
                    })
                    context.mentioned_locations = context.mentioned_locations[-10:]

                elif entity_type == "issue" and entity_value:
                    context.mentioned_issues.append({
                        "type": entity_value,
                        "timestamp": entry.timestamp.isoformat()
                    })
                    context.mentioned_issues = context.mentioned_issues[-10:]

        # Store media references
        if entry.image_url:
            context.uploaded_media.append({
                "type": "image",
                "url": entry.image_url,
                "analysis": entry.image_analysis,
                "timestamp": entry.timestamp.isoformat()
            })
            context.uploaded_media = context.uploaded_media[-10:]

        if entry.audio_url and entry.role == Role.USER.value:
            context.uploaded_media.append({
                "type": "audio",
                "url": entry.audio_url,
                "timestamp": entry.timestamp.isoformat()
            })
            context.uploaded_media = context.uploaded_media[-10:]

        # Update intent tracking
        if entry.intent:
            context.current_intent = entry.intent

        # Summarize old history if too long
        if len(context.history) > self.MAX_HISTORY_ENTRIES:
            await self._summarize_old_history(context)

        # Update timestamp and save
        context.updated_at = datetime.utcnow()
        await self._save_context(context)

        return context

    async def get_context_for_prompt(
        self,
        user_id: str,
        max_turns: int = 10,
        include_summary: bool = True
    ) -> str:
        """
        Format context for LLM prompt injection.

        Returns a formatted string suitable for injecting into agent prompts.
        """
        context = await self.get_context(user_id)
        prompt_parts = []

        # User profile section
        profile = context.user_profile
        if profile.name or profile.state:
            prompt_parts.append("=== User Profile ===")
            if profile.name:
                prompt_parts.append(f"Name: {profile.name}")
            if profile.state:
                location = profile.state
                if profile.lga:
                    location = f"{profile.lga}, {profile.state}"
                prompt_parts.append(f"Location: {location}")
            if profile.preferred_language != "en":
                prompt_parts.append(f"Language: {profile.preferred_language}")
            prompt_parts.append("")

        # Summary of older conversation
        if include_summary and context.history_summary:
            prompt_parts.append("=== Previous Context ===")
            prompt_parts.append(context.history_summary)
            prompt_parts.append("")

        # Recent conversation history
        recent = context.history[-max_turns:]
        if recent:
            prompt_parts.append("=== Recent Conversation ===")
            for entry in recent:
                prompt_parts.append(entry.format_for_prompt())
            prompt_parts.append("")

        # Active entities mentioned
        if context.mentioned_politicians:
            recent_politicians = list(set(context.mentioned_politicians[-5:]))
            prompt_parts.append(f"Politicians discussed: {', '.join(recent_politicians)}")

        if context.mentioned_issues:
            recent_issues = [i.get("type", "issue") for i in context.mentioned_issues[-3:]]
            prompt_parts.append(f"Issues raised: {', '.join(recent_issues)}")

        # Flow state
        if context.current_flow:
            prompt_parts.append(f"\nActive flow: {context.current_flow}")
            if context.flow_data:
                prompt_parts.append(f"Flow data: {json.dumps(context.flow_data)}")

        if context.pending_questions:
            prompt_parts.append(f"Waiting for user to answer: {context.pending_questions[0]}")

        return "\n".join(prompt_parts)

    async def update_user_profile(
        self,
        user_id: str,
        **updates
    ) -> ConversationContext:
        """Update user profile fields"""
        context = await self.get_context(user_id)

        for key, value in updates.items():
            if hasattr(context.user_profile, key):
                setattr(context.user_profile, key, value)

        context.updated_at = datetime.utcnow()
        await self._save_context(context)

        return context

    async def set_flow_state(
        self,
        user_id: str,
        flow_name: Optional[str],
        flow_data: Optional[Dict] = None,
        pending_question: Optional[str] = None
    ) -> ConversationContext:
        """Set active flow state for multi-step interactions"""
        context = await self.get_context(user_id)

        context.current_flow = flow_name
        context.flow_data = flow_data or {}
        context.pending_questions = [pending_question] if pending_question else []

        context.updated_at = datetime.utcnow()
        await self._save_context(context)

        return context

    async def clear_flow_state(self, user_id: str) -> ConversationContext:
        """Clear flow state after completion"""
        return await self.set_flow_state(user_id, None, None, None)

    async def start_voice_call(
        self,
        user_id: str,
        call_sid: str
    ) -> ConversationContext:
        """Mark user as in active voice call"""
        context = await self.get_context(user_id)

        context.in_active_call = True
        context.call_sid = call_sid
        context.call_start_time = datetime.utcnow()

        await self._save_context(context)
        return context

    async def end_voice_call(self, user_id: str) -> ConversationContext:
        """Mark voice call as ended"""
        context = await self.get_context(user_id)

        context.in_active_call = False
        context.call_sid = None
        context.call_start_time = None

        await self._save_context(context)
        return context

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _hash(self, value: str) -> str:
        """Hash a value for privacy"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    def _is_session_expired(self, context: ConversationContext) -> bool:
        """Check if session has expired (no activity for N minutes)"""
        if not context.session_start:
            return True

        timeout = timedelta(minutes=self.SESSION_TIMEOUT_MINUTES)
        return datetime.utcnow() - context.updated_at > timeout

    async def _start_new_session(self, context: ConversationContext):
        """Start a new session, clearing transient state"""
        context.session_id = self._generate_session_id()
        context.session_start = datetime.utcnow()
        context.current_flow = None
        context.flow_data = {}
        context.pending_questions = []
        # Keep user_profile, history, mentioned_* - those persist

    async def _get_from_cache(self, user_id: str) -> Optional[ConversationContext]:
        """Get context from hot storage (Redis or local)"""
        if self.redis:
            try:
                data = await self.redis.get(f"context:{user_id}")
                if data:
                    return ConversationContext.from_dict(json.loads(data))
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # Fallback to local cache
        return self._local_cache.get(user_id)

    async def _get_from_db(self, user_id: str) -> Optional[ConversationContext]:
        """Get context from cold storage (DB)"""
        if not self.db:
            return None

        try:
            # Implement based on your DB schema
            # result = await self.db.fetch_one(
            #     "SELECT * FROM conversation_contexts WHERE user_id = :user_id",
            #     {"user_id": user_id}
            # )
            # if result:
            #     return ConversationContext.from_dict(dict(result))
            pass
        except Exception as e:
            logger.error(f"DB get failed: {e}")

        return None

    async def _warm_cache(self, context: ConversationContext):
        """Load context into hot storage"""
        await self._save_to_cache(context)

    async def _save_context(self, context: ConversationContext):
        """Save context to both hot and cold storage"""
        await self._save_to_cache(context)
        await self._save_to_db(context)

    async def _save_to_cache(self, context: ConversationContext):
        """Save to hot storage (Redis or local)"""
        data = json.dumps(context.to_dict())

        if self.redis:
            try:
                await self.redis.setex(
                    f"context:{context.user_id}",
                    self.CONTEXT_TTL_HOURS * 3600,
                    data
                )
                return
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")

        # Fallback to local cache
        self._local_cache[context.user_id] = context

    async def _save_to_db(self, context: ConversationContext):
        """Save to cold storage (DB) - async, non-blocking"""
        if not self.db:
            return

        try:
            # Implement based on your DB schema
            # await self.db.execute(
            #     """INSERT INTO conversation_contexts (user_id, data, updated_at)
            #        VALUES (:user_id, :data, :updated_at)
            #        ON CONFLICT (user_id) DO UPDATE SET data = :data, updated_at = :updated_at""",
            #     {"user_id": context.user_id, "data": json.dumps(context.to_dict()), "updated_at": context.updated_at}
            # )
            pass
        except Exception as e:
            logger.error(f"DB save failed: {e}")

    async def _summarize_old_history(self, context: ConversationContext):
        """Summarize old history entries to save tokens"""
        if len(context.history) <= self.SUMMARIZE_THRESHOLD:
            return

        # Split history
        old_entries = context.history[:-30]
        context.history = context.history[-30:]

        # Generate summary
        if self.llm:
            try:
                summary = await self._generate_summary(old_entries)
                if context.history_summary:
                    context.history_summary = f"{context.history_summary}\n\n{summary}"
                else:
                    context.history_summary = summary
            except Exception as e:
                logger.error(f"Summary generation failed: {e}")
        else:
            # Simple text summary without LLM
            topics = set()
            for entry in old_entries:
                if entry.intent:
                    topics.add(entry.intent)

            summary = f"Previous conversation included: {', '.join(topics) if topics else 'general discussion'}"
            context.history_summary = summary

    async def _generate_summary(self, entries: List[ModalityEntry]) -> str:
        """Generate LLM summary of conversation entries"""
        if not self.llm:
            return ""

        # Format entries for summary
        text_parts = []
        for entry in entries:
            text_parts.append(entry.format_for_prompt())

        conversation_text = "\n".join(text_parts)

        # Call LLM for summary (implement based on your LLM client)
        # response = await self.llm.complete(
        #     prompt=f"Summarize this conversation in 2-3 sentences, focusing on key topics and user needs:\n\n{conversation_text}",
        #     max_tokens=150
        # )
        # return response.text

        return f"Conversation with {len(entries)} messages."


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global context manager - configure at app startup
context_manager = ContextManager()


def configure_context_manager(redis_client=None, db_client=None, llm_client=None):
    """Configure the global context manager"""
    context_manager.configure(redis_client, db_client, llm_client)
