"""
Agentic Retrieval System v2 for Decide9ja/Tade Chatbot.

Redesigned with:
1. Dynamic/implicit tool routing (not hard-coded groups)
2. Latest Claude models (Sonnet 4, Haiku 3.5) with 2024-2025 cutoffs
3. OpenAI fallback when Claude fails
4. Memory as a callable tool in the stack
5. Graceful degradation for out-of-scope intents
6. Web search integration (NOT eliminated)

Based on research from:
- https://arize.com/blog/best-practices-for-building-an-ai-agent-router/
- https://www.patronus.ai/ai-agent-development/ai-agent-routing
- https://platform.claude.com/docs/en/about-claude/models/overview

Author: Decide9ja Team
"""
import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL CONFIGURATION - Use latest models with recent knowledge cutoffs
# =============================================================================

# Claude models - Updated January 2025 knowledge cutoff
CLAUDE_MODELS = {
    "fast": "claude-3-5-haiku-20241022",      # July 2024 cutoff, fast & cheap
    "balanced": "claude-sonnet-4-20250514",    # January 2025 cutoff, balanced
    "powerful": "claude-opus-4-1-20250805",    # January 2025 cutoff, most capable
}

# OpenAI models - Fallback
OPENAI_MODELS = {
    "fast": "gpt-4o-mini",
    "balanced": "gpt-4o",
    "powerful": "gpt-4-turbo",
}

# Default model tier for routing
DEFAULT_MODEL_TIER = "fast"  # Use fast for routing, balanced for generation


# =============================================================================
# TOOL DEFINITIONS - Dynamic, not hard-coded groups
# =============================================================================

@dataclass
class Tool:
    """A callable tool in the agentic system."""
    name: str
    description: str
    keywords: List[str]              # For semantic matching
    executor: Callable               # The function to call
    requires_context: List[str] = field(default_factory=list)  # e.g., ["state", "lga"]
    can_handoff_to: List[str] = field(default_factory=list)    # Tools it can transfer to
    is_fallback: bool = False        # Is this a fallback tool?
    priority: int = 5                # 1-10, higher = more specific


@dataclass
class ToolResult:
    """Result from executing a tool."""
    tool_name: str
    success: bool
    data: Any
    confidence: float               # 0-1, how confident in the result
    source: str                     # Where the data came from
    error: Optional[str] = None
    handoff_to: Optional[str] = None  # Suggest handoff to another tool
    metadata: Dict = field(default_factory=dict)


class RetrievalStatus(Enum):
    """Status of retrieval attempt."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    FALLBACK = "fallback"
    HANDOFF = "handoff"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class AgenticResult:
    """Final result from agentic retrieval."""
    original_query: str
    final_query: str
    tool_results: List[ToolResult]
    graded_context: str
    sources_used: List[str]
    confidence: float
    total_attempts: int
    status: RetrievalStatus
    model_used: str
    fallback_used: bool = False


# =============================================================================
# LLM PROVIDER ABSTRACTION - Claude + OpenAI fallback
# =============================================================================

class LLMProvider(ABC):
    """Abstract LLM provider for routing and generation."""

    @abstractmethod
    async def complete(self, prompt: str, max_tokens: int = 200) -> str:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model_tier: str = "fast"):
        self.model = CLAUDE_MODELS.get(model_tier, CLAUDE_MODELS["fast"])
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    async def complete(self, prompt: str, max_tokens: int = 200) -> str:
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude error: {e}")
            raise

    async def is_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))


class OpenAIProvider(LLMProvider):
    """OpenAI provider as fallback."""

    def __init__(self, model_tier: str = "fast"):
        self.model = OPENAI_MODELS.get(model_tier, OPENAI_MODELS["fast"])
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    async def complete(self, prompt: str, max_tokens: int = 200) -> str:
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise

    async def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))


async def get_llm_provider(tier: str = "fast", prefer_claude: bool = True) -> Tuple[LLMProvider, str]:
    """
    Get an available LLM provider with fallback.
    Returns (provider, provider_name).
    """
    claude = ClaudeProvider(tier)
    openai = OpenAIProvider(tier)

    if prefer_claude and await claude.is_available():
        return claude, "claude"
    elif await openai.is_available():
        return openai, "openai"
    elif await claude.is_available():
        return claude, "claude"
    else:
        raise RuntimeError("No LLM provider available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")


# =============================================================================
# TOOL REGISTRY - Dynamic tool discovery
# =============================================================================

class ToolRegistry:
    """
    Dynamic tool registry with semantic matching.
    Tools are discovered implicitly, not hard-grouped.
    """

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._embeddings_cache: Dict[str, List[float]] = {}

    def register(self, tool: Tool):
        """Register a tool in the registry."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self.tools.values())

    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions for LLM routing."""
        descriptions = []
        for tool in sorted(self.tools.values(), key=lambda t: -t.priority):
            keywords = ", ".join(tool.keywords[:5])
            descriptions.append(f"- {tool.name}: {tool.description} (keywords: {keywords})")
        return "\n".join(descriptions)

    async def find_relevant_tools(
        self,
        query: str,
        max_tools: int = 3
    ) -> List[Tuple[Tool, float]]:
        """
        Find relevant tools for a query using keyword matching + semantic similarity.
        Returns list of (tool, relevance_score) tuples.
        """
        query_lower = query.lower()
        scores = []

        for tool in self.tools.values():
            score = 0.0

            # Keyword matching (fast)
            for keyword in tool.keywords:
                if keyword.lower() in query_lower:
                    score += 0.3

            # Description matching
            if any(word in tool.description.lower() for word in query_lower.split()):
                score += 0.2

            # Priority boost
            score += tool.priority * 0.05

            if score > 0:
                scores.append((tool, min(score, 1.0)))

        # Sort by score descending
        scores.sort(key=lambda x: -x[1])
        return scores[:max_tools]

    def get_fallback_tools(self) -> List[Tool]:
        """Get tools marked as fallback."""
        return [t for t in self.tools.values() if t.is_fallback]


# Global registry
tool_registry = ToolRegistry()


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def _tool_politician_lookup(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Look up politician by name or position."""
    from app.services.intelligent_retrieval import (
        _lookup_politician_by_name,
        _lookup_politician_by_position
    )

    try:
        politician_name = entities.get("politician_name", "")
        position = entities.get("position", "")
        state = context.get("state")

        result = None

        if politician_name:
            result = await _lookup_politician_by_name(politician_name)
        elif position:
            result = await _lookup_politician_by_position(position, state)

        if result:
            content = f"{result['name']} - {result.get('position', 'Unknown position')}. Party: {result.get('party', 'Unknown')}. {result.get('bio', '')}"
            return ToolResult(
                tool_name="politician_lookup",
                success=True,
                data=result,
                confidence=0.85,
                source="politicians_db",
                metadata={"type": "politician"}
            )
        else:
            return ToolResult(
                tool_name="politician_lookup",
                success=False,
                data=None,
                confidence=0.0,
                source="politicians_db",
                error="No politician found",
                handoff_to="web_search"  # Suggest handoff
            )

    except Exception as e:
        logger.error(f"Politician lookup error: {e}")
        return ToolResult(
            tool_name="politician_lookup",
            success=False,
            data=None,
            confidence=0.0,
            source="politicians_db",
            error=str(e),
            handoff_to="web_search"
        )


async def _tool_representative_lookup(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Look up user's representatives by state/LGA."""
    from app.services.intelligent_retrieval import _lookup_representatives

    try:
        state = context.get("state")
        lga = context.get("lga")

        if not state or not lga:
            return ToolResult(
                tool_name="representative_lookup",
                success=False,
                data=None,
                confidence=0.0,
                source="lga_representatives",
                error="Need user's state and LGA to look up representatives"
            )

        reps = await _lookup_representatives(state, lga)

        if reps:
            content = "\n".join([
                f"• {r['position']}: {r['name']} ({r['party']}) - {r.get('area', '')}"
                for r in reps
            ])
            return ToolResult(
                tool_name="representative_lookup",
                success=True,
                data=reps,
                confidence=0.9,
                source="lga_representatives",
                metadata={"type": "representatives", "count": len(reps)}
            )
        else:
            return ToolResult(
                tool_name="representative_lookup",
                success=False,
                data=None,
                confidence=0.0,
                source="lga_representatives",
                error="No representatives found for this LGA"
            )

    except Exception as e:
        logger.error(f"Representative lookup error: {e}")
        return ToolResult(
            tool_name="representative_lookup",
            success=False,
            data=None,
            confidence=0.0,
            source="lga_representatives",
            error=str(e)
        )


async def _tool_web_search(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Search the web for current news and events."""
    from app.services.intelligent_retrieval import _search_web

    try:
        # Always add Nigeria context for relevant queries
        search_query = query
        if "nigeria" not in query.lower():
            search_query = f"{query} Nigeria"

        results = await _search_web(search_query, limit=5)

        if results:
            return ToolResult(
                tool_name="web_search",
                success=True,
                data=results,
                confidence=0.75,
                source="web_search",
                metadata={"type": "news", "count": len(results)}
            )
        else:
            return ToolResult(
                tool_name="web_search",
                success=False,
                data=None,
                confidence=0.0,
                source="web_search",
                error="No web results found",
                handoff_to="knowledge_base"
            )

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return ToolResult(
            tool_name="web_search",
            success=False,
            data=None,
            confidence=0.0,
            source="web_search",
            error=str(e)
        )


async def _tool_knowledge_base(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Search RAG knowledge base for background information."""
    from app.services.intelligent_retrieval import _search_rag

    try:
        rag_context = await _search_rag(query, limit=5)

        if rag_context and not rag_context.startswith("NO"):
            return ToolResult(
                tool_name="knowledge_base",
                success=True,
                data=rag_context,
                confidence=0.7,
                source="rag_documents",
                metadata={"type": "knowledge"}
            )
        else:
            return ToolResult(
                tool_name="knowledge_base",
                success=False,
                data=None,
                confidence=0.0,
                source="rag_documents",
                error="No relevant documents found"
            )

    except Exception as e:
        logger.error(f"Knowledge base error: {e}")
        return ToolResult(
            tool_name="knowledge_base",
            success=False,
            data=None,
            confidence=0.0,
            source="rag_documents",
            error=str(e)
        )


async def _tool_memory_retrieval(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Retrieve relevant context from user's conversation memory."""
    try:
        from app.services.enhanced_memory import enhanced_memory

        phone = context.get("phone", "")
        if not phone:
            return ToolResult(
                tool_name="memory_retrieval",
                success=False,
                data=None,
                confidence=0.0,
                source="user_memory",
                error="No phone context available"
            )

        # Get personalization context
        personalization = enhanced_memory.get_personalization_context(phone)

        # Get semantically relevant past conversations
        relevant_past = enhanced_memory.get_relevant_context(phone, query, max_context=3)

        # Get recent episodes
        episodes = enhanced_memory.get_recent_episodes(phone, limit=2)

        memory_data = {
            "personalization": personalization,
            "relevant_past": relevant_past,
            "episodes": episodes
        }

        has_data = bool(personalization or relevant_past or episodes)

        return ToolResult(
            tool_name="memory_retrieval",
            success=has_data,
            data=memory_data,
            confidence=0.6 if has_data else 0.0,
            source="user_memory",
            metadata={"type": "memory", "has_episodes": bool(episodes)}
        )

    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return ToolResult(
            tool_name="memory_retrieval",
            success=False,
            data=None,
            confidence=0.0,
            source="user_memory",
            error=str(e)
        )


async def _tool_election_info(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Get 2027 election information, candidates, polls."""
    try:
        from app.services.election_2027.candidate_tracker import get_candidate_tracker, get_candidate

        tracker = get_candidate_tracker()
        candidate_name = entities.get("candidate_name", "")

        if candidate_name:
            candidate = get_candidate(candidate_name)
            if candidate:
                return ToolResult(
                    tool_name="election_info",
                    success=True,
                    data={"name": candidate.name, "party": candidate.party, "bio": candidate.bio},
                    confidence=0.85,
                    source="candidate_tracker",
                    metadata={"type": "candidate"}
                )

        # Get all presidential candidates
        candidates = tracker.get_presidential_candidates()
        if candidates:
            return ToolResult(
                tool_name="election_info",
                success=True,
                data=[{"name": c.name, "party": c.party} for c in candidates],
                confidence=0.8,
                source="candidate_tracker",
                metadata={"type": "candidate_list", "count": len(candidates)}
            )

        return ToolResult(
            tool_name="election_info",
            success=False,
            data=None,
            confidence=0.0,
            source="candidate_tracker",
            error="No election data found",
            handoff_to="web_search"
        )

    except Exception as e:
        logger.error(f"Election info error: {e}")
        return ToolResult(
            tool_name="election_info",
            success=False,
            data=None,
            confidence=0.0,
            source="candidate_tracker",
            error=str(e)
        )


async def _tool_fallback(query: str, entities: Dict, context: Dict) -> ToolResult:
    """Fallback tool when nothing else matches - uses LLM knowledge."""
    return ToolResult(
        tool_name="fallback",
        success=True,
        data={"message": "Using LLM general knowledge for this query"},
        confidence=0.4,
        source="llm_knowledge",
        metadata={"type": "fallback", "reason": "No specific tool matched"}
    )


# =============================================================================
# REGISTER ALL TOOLS
# =============================================================================

def _register_default_tools():
    """Register all default tools."""

    tool_registry.register(Tool(
        name="politician_lookup",
        description="Look up information about Nigerian politicians by name or position (president, governor, senator, minister)",
        keywords=["who is", "politician", "president", "governor", "senator", "minister", "rep", "APC", "PDP", "LP", "party", "bio", "profile"],
        executor=_tool_politician_lookup,
        can_handoff_to=["web_search", "knowledge_base"],
        priority=8
    ))

    tool_registry.register(Tool(
        name="representative_lookup",
        description="Find user's elected representatives based on their state and LGA (senator, governor, house rep)",
        keywords=["my senator", "my governor", "my representative", "who represents", "my rep", "my constituency"],
        executor=_tool_representative_lookup,
        requires_context=["state", "lga"],
        priority=9
    ))

    tool_registry.register(Tool(
        name="web_search",
        description="Search for current news, recent events, and live updates about Nigerian politics",
        keywords=["news", "latest", "recent", "update", "today", "happening", "trending", "current", "breaking"],
        executor=_tool_web_search,
        can_handoff_to=["knowledge_base"],
        priority=7
    ))

    tool_registry.register(Tool(
        name="knowledge_base",
        description="Search background knowledge, history, policies, constitution, and educational content",
        keywords=["explain", "what is", "how does", "history", "policy", "law", "constitution", "budget", "meaning", "definition"],
        executor=_tool_knowledge_base,
        can_handoff_to=["web_search"],
        priority=6
    ))

    tool_registry.register(Tool(
        name="memory_retrieval",
        description="Retrieve user's conversation history, preferences, and past interactions for personalization",
        keywords=["remember", "we discussed", "last time", "you said", "my preference", "earlier"],
        executor=_tool_memory_retrieval,
        requires_context=["phone"],
        priority=5
    ))

    tool_registry.register(Tool(
        name="election_info",
        description="Information about 2027 elections, candidates, polls, and voting",
        keywords=["2027", "election", "candidate", "running for", "vote", "poll", "INEC", "campaign"],
        executor=_tool_election_info,
        can_handoff_to=["web_search", "politician_lookup"],
        priority=7
    ))

    tool_registry.register(Tool(
        name="fallback",
        description="General fallback when no specific tool matches - uses LLM knowledge",
        keywords=[],
        executor=_tool_fallback,
        is_fallback=True,
        priority=1
    ))


# Initialize default tools
_register_default_tools()


# =============================================================================
# DYNAMIC ROUTING - Implicit intent classification
# =============================================================================

async def route_to_tools(
    query: str,
    context: Dict = None,
    provider: LLMProvider = None
) -> List[Tuple[str, Dict, float]]:
    """
    Dynamically route query to relevant tools.
    Returns list of (tool_name, entities, confidence) tuples.

    Uses hybrid approach:
    1. Keyword matching (fast)
    2. LLM classification (if needed)
    3. Graceful fallback
    """
    context = context or {}

    # Step 1: Fast keyword matching
    matched_tools = await tool_registry.find_relevant_tools(query, max_tools=3)

    if matched_tools and matched_tools[0][1] >= 0.5:
        # High confidence keyword match
        results = []
        for tool, score in matched_tools:
            entities = await _extract_entities_fast(query, tool.name)
            results.append((tool.name, entities, score))
        logger.info(f"Fast routing matched: {[r[0] for r in results]}")
        return results

    # Step 2: LLM classification for ambiguous queries
    if provider is None:
        provider, _ = await get_llm_provider("fast")

    tool_descriptions = tool_registry.get_tool_descriptions()

    prompt = f"""You are routing a user query to the most relevant tools.

AVAILABLE TOOLS:
{tool_descriptions}

USER QUERY: "{query}"

USER CONTEXT:
- State: {context.get('state', 'Unknown')}
- LGA: {context.get('lga', 'Unknown')}

Analyze the query and select 1-3 most relevant tools. Extract any entities.

Respond in JSON:
{{
    "tools": [
        {{
            "name": "tool_name",
            "confidence": 0.0-1.0,
            "entities": {{"key": "value"}},
            "reasoning": "brief reason"
        }}
    ],
    "is_out_of_scope": false,
    "fallback_reason": null
}}

If the query is completely unrelated to Nigerian politics/governance, set is_out_of_scope=true.
If no tool fits well but it's related to politics, include "fallback" tool."""

    try:
        response = await provider.complete(prompt, max_tokens=300)

        # Parse JSON
        if "```" in response:
            response = response.split("```json")[-1].split("```")[0]

        data = json.loads(response)

        results = []
        for tool_data in data.get("tools", []):
            tool_name = tool_data.get("name", "fallback")
            confidence = float(tool_data.get("confidence", 0.5))
            entities = tool_data.get("entities", {})

            # Verify tool exists
            if tool_registry.get_tool(tool_name):
                results.append((tool_name, entities, confidence))

        # Handle out of scope
        if data.get("is_out_of_scope"):
            return [("fallback", {"out_of_scope": True, "reason": data.get("fallback_reason")}, 0.3)]

        # Always have at least fallback
        if not results:
            results = [("fallback", {}, 0.3)]

        logger.info(f"LLM routing: {[r[0] for r in results]}")
        return results

    except Exception as e:
        logger.error(f"LLM routing error: {e}")
        # Graceful fallback to keyword matches or general fallback
        if matched_tools:
            return [(matched_tools[0][0].name, {}, matched_tools[0][1])]
        return [("fallback", {"error": str(e)}, 0.2)]


async def _extract_entities_fast(query: str, tool_name: str) -> Dict:
    """Fast entity extraction using patterns."""
    entities = {}
    query_lower = query.lower()

    if tool_name == "politician_lookup":
        # Extract politician names (capitalized words)
        words = query.split()
        potential_names = [w for w in words if w[0].isupper() and len(w) > 2]
        if potential_names:
            entities["politician_name"] = " ".join(potential_names[:2])

        # Extract positions
        positions = ["president", "governor", "senator", "minister", "rep"]
        for pos in positions:
            if pos in query_lower:
                entities["position"] = pos

    elif tool_name == "election_info":
        # Extract candidate names
        if "follow" in query_lower or "candidate" in query_lower:
            words = query.split()
            for i, w in enumerate(words):
                if w.lower() in ["follow", "unfollow"] and i + 1 < len(words):
                    entities["candidate_name"] = words[i + 1]

    return entities


# =============================================================================
# GRACEFUL DEGRADATION
# =============================================================================

async def graceful_degrade(
    query: str,
    failed_tools: List[str],
    context: Dict,
    provider: LLMProvider = None
) -> Tuple[str, str]:
    """
    Handle graceful degradation when tools fail.
    Returns (fallback_response, reason).
    """
    if provider is None:
        provider, _ = await get_llm_provider("fast")

    prompt = f"""A user asked about Nigerian politics but our tools couldn't find specific information.

QUERY: "{query}"
TOOLS TRIED: {', '.join(failed_tools)}
USER STATE: {context.get('state', 'Unknown')}

Generate a helpful response that:
1. Acknowledges we don't have specific data
2. Provides general knowledge if applicable
3. Suggests how the user might find more info
4. Keeps the Nigerian political context

Be conversational, not robotic. 2-3 sentences max."""

    try:
        response = await provider.complete(prompt, max_tokens=200)
        return response, "graceful_degradation"
    except:
        return (
            "I don't have specific information about that right now, but I can help you explore related topics. What aspect would you like to know more about?",
            "default_fallback"
        )


# =============================================================================
# MAIN AGENTIC RETRIEVAL
# =============================================================================

async def agentic_retrieve(
    query: str,
    user_context: Dict = None
) -> AgenticResult:
    """
    Main entry point for agentic retrieval.

    Flow:
    1. Get LLM provider (Claude preferred, OpenAI fallback)
    2. Dynamic routing to relevant tools
    3. Execute tools with handoff support
    4. Grade and combine results
    5. Graceful degradation if needed
    """
    user_context = user_context or {}
    tool_results = []
    sources_used = []
    fallback_used = False

    # Step 1: Get LLM provider
    try:
        provider, provider_name = await get_llm_provider("fast")
    except RuntimeError as e:
        logger.error(f"No LLM provider: {e}")
        return AgenticResult(
            original_query=query,
            final_query=query,
            tool_results=[],
            graded_context="LLM provider unavailable",
            sources_used=[],
            confidence=0.0,
            total_attempts=0,
            status=RetrievalStatus.FAILED,
            model_used="none",
            fallback_used=True
        )

    # Step 2: Route to tools
    routed_tools = await route_to_tools(query, user_context, provider)

    # Step 3: Execute tools
    executed = set()
    max_attempts = 5  # Prevent infinite loops

    for attempt in range(max_attempts):
        if not routed_tools:
            break

        tool_name, entities, confidence = routed_tools.pop(0)

        if tool_name in executed:
            continue
        executed.add(tool_name)

        tool = tool_registry.get_tool(tool_name)
        if not tool:
            continue

        # Check required context
        missing_context = [c for c in tool.requires_context if not user_context.get(c)]
        if missing_context:
            logger.warning(f"Tool {tool_name} missing context: {missing_context}")
            continue

        # Execute tool
        try:
            result = await tool.executor(query, entities, user_context)
            tool_results.append(result)

            if result.success:
                sources_used.append(result.source)
            elif result.handoff_to and result.handoff_to not in executed:
                # Add handoff tool to queue
                routed_tools.insert(0, (result.handoff_to, entities, confidence * 0.8))

        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            tool_results.append(ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                confidence=0.0,
                source=tool_name,
                error=str(e)
            ))

    # Step 4: Determine status and confidence
    successful_results = [r for r in tool_results if r.success]
    failed_tools = [r.tool_name for r in tool_results if not r.success]

    if successful_results:
        max_confidence = max(r.confidence for r in successful_results)
        status = RetrievalStatus.SUCCESS if max_confidence >= 0.6 else RetrievalStatus.PARTIAL
    elif tool_results:
        status = RetrievalStatus.FAILED
        max_confidence = 0.0
    else:
        status = RetrievalStatus.OUT_OF_SCOPE
        max_confidence = 0.0

    # Step 5: Graceful degradation if needed
    graded_context = ""
    if successful_results:
        graded_context = _format_tool_results(successful_results)
    elif failed_tools:
        fallback_response, reason = await graceful_degrade(query, failed_tools, user_context, provider)
        graded_context = f"[FALLBACK] {fallback_response}"
        status = RetrievalStatus.FALLBACK
        fallback_used = True

    return AgenticResult(
        original_query=query,
        final_query=query,
        tool_results=tool_results,
        graded_context=graded_context,
        sources_used=sources_used,
        confidence=max_confidence,
        total_attempts=len(tool_results),
        status=status,
        model_used=provider_name,
        fallback_used=fallback_used
    )


def _format_tool_results(results: List[ToolResult]) -> str:
    """Format successful tool results into context string."""
    parts = []

    for result in results:
        if not result.success:
            continue

        data = result.data
        source = result.source.upper()
        confidence = "HIGH" if result.confidence >= 0.7 else "MEDIUM" if result.confidence >= 0.5 else "LOW"

        if isinstance(data, str):
            parts.append(f"[{source}] ({confidence})\n{data}")
        elif isinstance(data, dict):
            if "content" in data:
                parts.append(f"[{source}] ({confidence})\n{data['content']}")
            elif "message" in data:
                parts.append(f"[{source}] ({confidence})\n{data['message']}")
            else:
                # Format dict as key-value pairs
                formatted = "\n".join([f"  {k}: {v}" for k, v in data.items() if v])
                parts.append(f"[{source}] ({confidence})\n{formatted}")
        elif isinstance(data, list):
            items = []
            for item in data[:5]:  # Max 5 items
                if isinstance(item, dict):
                    if "title" in item:
                        items.append(f"• {item['title']}: {item.get('summary', '')[:150]}")
                    elif "name" in item:
                        items.append(f"• {item['name']}: {item.get('party', '')} - {item.get('position', '')}")
                    else:
                        items.append(f"• {str(item)[:150]}")
                else:
                    items.append(f"• {str(item)[:150]}")
            parts.append(f"[{source}] ({confidence})\n" + "\n".join(items))

    return "\n\n---\n\n".join(parts) if parts else "No relevant information found."


# =============================================================================
# HELPER FOR MESSAGE HANDLER INTEGRATION
# =============================================================================

async def get_agentic_context(
    query: str,
    user_state: str = None,
    user_lga: str = None,
    user_name: str = None,
    phone: str = None
) -> Tuple[str, List[str], bool]:
    """
    Helper function to get agentic retrieval context.
    Returns (context_string, sources_used, success).
    """
    user_context = {
        "state": user_state,
        "lga": user_lga,
        "name": user_name,
        "phone": phone
    }

    result = await agentic_retrieve(query, user_context)

    return (
        result.graded_context,
        result.sources_used,
        result.status in [RetrievalStatus.SUCCESS, RetrievalStatus.PARTIAL]
    )
