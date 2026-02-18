"""
Decide9ja Multi-Agent Base Classes
==================================
All agents inherit from BaseAgent and follow these protocols.

Architecture: Database First, LLM Last
- 80% of queries should be answered from database + cache (FREE)
- LLM only for ambiguous classification and complex responses
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from enum import Enum
from datetime import datetime
import hashlib
import json


class AgentTier(Enum):
    """Agent tiers for organization and priority"""
    ENTRY = 1          # Gatekeeper, Classifier, Router
    CORE = 2           # Rep lookup, Politician, Promise, Election, News
    MULTIMODAL = 3     # Voice, Image, Location
    REPORTING = 4      # Issue intake, tracking
    OUTPUT = 5         # Response formatting
    ANALYTICS = 6      # B2B data collection


class CostLevel(Enum):
    """Cost level for budget management"""
    FREE = 0           # No LLM call (database, cache, rules)
    CHEAP = 1          # Small/fast model (Haiku, classification)
    MEDIUM = 2         # Standard model (Sonnet)
    EXPENSIVE = 3      # Large model (Opus) - avoid unless necessary


@dataclass
class UserContext:
    """Everything we know about the user"""
    phone_hash: str                    # Hashed phone for privacy
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    ward: Optional[str] = None
    language: str = "en"               # en, pcm (pidgin), ha, yo, ig
    is_new_user: bool = False
    is_verified: bool = False          # Journalist, official, etc.
    preferences: Dict = field(default_factory=dict)
    history_summary: Optional[str] = None
    followed_politicians: List[str] = field(default_factory=list)
    reported_issues: List[str] = field(default_factory=list)


@dataclass
class AgentInput:
    """Standardized input to any agent"""
    # Core message
    message_id: str
    raw_text: str
    timestamp: datetime

    # User context
    user: UserContext

    # Classification (filled by ClassifierAgent)
    intent: Optional[str] = None
    confidence: float = 0.0
    entities: Dict = field(default_factory=dict)

    # Media attachments
    voice_url: Optional[str] = None
    audio_url: Optional[str] = None    # Alias for voice_url (WhatsApp uses audio)
    image_url: Optional[str] = None    # Single image URL
    image_urls: List[str] = field(default_factory=list)  # Multiple images
    video_url: Optional[str] = None
    document_url: Optional[str] = None
    location: Optional[Dict] = None    # {lat, lng, address}

    # Routing metadata
    source_agent: Optional[str] = None
    handoff_reason: Optional[str] = None
    retrieval_context: Optional[Dict] = None

    # General context for agent-to-agent data passing
    context: Optional[Dict] = None     # Multimodal context, preprocessed data, etc.

    # For analytics
    session_id: Optional[str] = None
    conversation_turn: int = 0

    def cache_key(self) -> str:
        """Generate cache key for this query"""
        # Normalize and hash the query + key context
        normalized = f"{self.intent}:{self.raw_text.lower().strip()}:{self.user.state}:{self.user.lga}"
        return hashlib.md5(normalized.encode()).hexdigest()


@dataclass
class AgentOutput:
    """Standardized output from any agent"""
    success: bool

    # Response content
    response_text: Optional[str] = None
    response_voice: Optional[str] = None   # URL to audio file
    response_media: List[str] = field(default_factory=list)

    # Structured data (for downstream agents)
    data: Dict = field(default_factory=dict)

    # Routing
    handoff_to: Optional[str] = None
    handoff_reason: Optional[str] = None

    # For response formatting
    buttons: List[Dict] = field(default_factory=list)  # [{text, callback}]
    list_items: List[str] = field(default_factory=list)
    template_name: Optional[str] = None

    # Metadata
    sources: List[str] = field(default_factory=list)   # Citations
    confidence: float = 1.0
    cost_level: CostLevel = CostLevel.FREE
    cached: bool = False

    # Analytics tags (for B2B)
    analytics_tags: Dict = field(default_factory=dict)
    # e.g., {"topic": "education", "sentiment": "negative", "politician_mentioned": "tinubu"}

    # Errors
    error: Optional[str] = None
    error_code: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all Decide9ja agents.

    Every agent must:
    1. Have a unique name
    2. Declare what intents it handles
    3. Declare its cost level
    4. Implement can_handle() and handle()
    """

    # Override in subclass
    name: str = "base_agent"
    description: str = "Base agent - do not use directly"
    tier: AgentTier = AgentTier.CORE
    cost_level: CostLevel = CostLevel.FREE
    handled_intents: List[str] = []

    def __init__(self, db_client=None, cache=None, llm_client=None):
        self.db = db_client
        self.cache = cache
        self.llm = llm_client
        self._call_count = 0
        self._cache_hits = 0

    @abstractmethod
    async def can_handle(self, input: AgentInput) -> bool:
        """
        Return True if this agent can handle the input.
        Should be fast (no LLM calls).
        """
        pass

    @abstractmethod
    async def handle(self, input: AgentInput) -> AgentOutput:
        """
        Process the input and return output.

        Pattern:
        1. Check cache first
        2. Try database lookup
        3. Only call LLM if necessary
        4. Cache the result
        5. Tag for analytics
        """
        pass

    async def _check_cache(self, input: AgentInput) -> Optional[AgentOutput]:
        """Check if we have a cached response"""
        if not self.cache:
            return None

        key = f"{self.name}:{input.cache_key()}"
        cached = await self.cache.get(key)

        if cached:
            self._cache_hits += 1
            # Filter to only known AgentOutput fields to avoid unknown kwarg errors
            cached_dict = json.loads(cached)
            valid_fields = {
                "success", "response_text", "response_voice", "response_media",
                "data", "handoff_to", "handoff_reason", "buttons", "list_items",
                "template_name", "sources", "confidence", "cost_level", "cached",
                "analytics_tags", "error", "error_code"
            }
            filtered = {k: v for k, v in cached_dict.items() if k in valid_fields}
            output = AgentOutput(**filtered)
            output.cached = True
            return output

        return None

    async def _save_cache(self, input: AgentInput, output: AgentOutput, ttl: int = 3600):
        """Cache a response"""
        if not self.cache or not output.success:
            return

        key = f"{self.name}:{input.cache_key()}"
        # Convert output to dict, handling enums
        output_dict = {
            "success": output.success,
            "response_text": output.response_text,
            "response_voice": output.response_voice,
            "response_media": output.response_media,
            "data": output.data,
            "handoff_to": output.handoff_to,
            "handoff_reason": output.handoff_reason,
            "buttons": output.buttons,
            "list_items": output.list_items,
            "template_name": output.template_name,
            "sources": output.sources,
            "confidence": output.confidence,
            "cost_level": output.cost_level.value if isinstance(output.cost_level, CostLevel) else output.cost_level,
            "cached": output.cached,
            "analytics_tags": output.analytics_tags,
            "error": output.error,
            "error_code": output.error_code,
        }
        await self.cache.set(key, json.dumps(output_dict), ttl=ttl)

    def _tag_analytics(self, input: AgentInput, output: AgentOutput) -> AgentOutput:
        """Add analytics tags for B2B data collection"""
        output.analytics_tags.update({
            "agent": self.name,
            "intent": input.intent,
            "state": input.user.state,
            "lga": input.user.lga,
            "timestamp": input.timestamp.isoformat(),
            "cached": output.cached,
            "cost_level": output.cost_level.value if isinstance(output.cost_level, CostLevel) else output.cost_level,
        })
        return output

    def handoff(self, target_agent: str, reason: str, data: Dict = None) -> AgentOutput:
        """Create a handoff response"""
        return AgentOutput(
            success=True,
            handoff_to=target_agent,
            handoff_reason=reason,
            data=data or {}
        )

    def fail(self, error: str, error_code: str = "UNKNOWN") -> AgentOutput:
        """Create a failure response"""
        return AgentOutput(
            success=False,
            error=error,
            error_code=error_code
        )

    def respond(self, text: str, **kwargs) -> AgentOutput:
        """Create a success response with text"""
        return AgentOutput(
            success=True,
            response_text=text,
            cost_level=kwargs.get("cost_level", CostLevel.FREE),
            sources=kwargs.get("sources", []),
            buttons=kwargs.get("buttons", []),
            data=kwargs.get("data", {}),
            analytics_tags=kwargs.get("analytics_tags", {})
        )

    def stats(self) -> Dict:
        """Return agent statistics"""
        return {
            "name": self.name,
            "calls": self._call_count,
            "cache_hits": self._cache_hits,
            "cache_rate": self._cache_hits / max(self._call_count, 1)
        }


class DatabaseAgent(BaseAgent):
    """
    Base class for agents that primarily query the database.
    LLM is only used to format the response, not to find information.

    Cost: FREE for most queries
    """

    cost_level = CostLevel.FREE  # Most queries don't need LLM

    @abstractmethod
    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """
        Query the database for the answer.
        Return None if not found.
        """
        pass

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # 1. Check cache
        cached = await self._check_cache(input)
        if cached:
            return self._tag_analytics(input, cached)

        # 2. Query database
        db_result = await self.query_database(input)

        if db_result:
            # Format response (may or may not need LLM)
            output = await self.format_response(input, db_result)
        else:
            # Handoff to web search or fallback
            output = self.handoff(
                target_agent="fallback",
                reason="not_in_database",
                data={"original_query": input.raw_text}
            )

        # 3. Cache and tag
        if output.success and not output.handoff_to:
            await self._save_cache(input, output)

        return self._tag_analytics(input, output)

    async def format_response(self, input: AgentInput, data: Dict) -> AgentOutput:
        """
        Format database result into user-friendly response.
        Override for custom formatting. Default uses templates.
        """
        # Default: use template-based formatting (no LLM)
        return AgentOutput(
            success=True,
            data=data,
            cost_level=CostLevel.FREE
        )


class LLMAgent(BaseAgent):
    """
    Base class for agents that need LLM for reasoning.
    Use sparingly - these cost money.

    Cost: MEDIUM (default) or EXPENSIVE
    """

    cost_level = CostLevel.MEDIUM

    # Override in subclass
    system_prompt: str = ""
    max_tokens: int = 500
    temperature: float = 0.3
    model: str = "gpt-4o-mini"  # Default to OpenAI (Anthropic credits depleted)

    async def call_llm(self, user_prompt: str, context: Dict = None) -> str:
        """Call the LLM with this agent's system prompt"""
        import os
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        client = AsyncOpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=messages
        )

        return response.choices[0].message.content or ""

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # 1. Check cache first
        cached = await self._check_cache(input)
        if cached:
            return self._tag_analytics(input, cached)

        # 2. Call LLM
        try:
            response = await self.process_with_llm(input)
            output = self.respond(
                response,
                cost_level=self.cost_level
            )
        except Exception as e:
            output = self.fail(str(e), "LLM_ERROR")

        # 3. Cache successful responses
        if output.success:
            await self._save_cache(input, output)

        return self._tag_analytics(input, output)

    async def process_with_llm(self, input: AgentInput) -> str:
        """
        Override this to customize LLM processing.
        Default just passes the raw text to the LLM.
        """
        return await self.call_llm(input.raw_text)
