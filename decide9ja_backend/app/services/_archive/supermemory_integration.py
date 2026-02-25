"""
Supermemory Integration for Decide9ja

Production-ready integration with Supermemory for:
- Cross-session persistence (memories survive restarts/deploys)
- Automatic user profiling from interactions
- Semantic recall with sub-300ms latency
- Continuous learning from user feedback
- Knowledge graph augmentation

API Docs: https://supermemory.ai/docs
Console: https://console.supermemory.ai

Usage:
    from app.services.supermemory_integration import SuperMemoryClient

    # Initialize client
    memory = SuperMemoryClient()

    # Store interaction
    await memory.add_memory(
        user_id=phone_hash,
        content=f"User asked: {question}\\nAgent responded: {response}",
        metadata={"intent": intent, "entities": entities}
    )

    # Recall context for new query
    context = await memory.search_memories(
        user_id=phone_hash,
        query=new_question,
        limit=5
    )

    # Get user profile
    profile = await memory.get_user_profile(phone_hash)
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment
SUPERMEMORY_API_KEY = os.getenv("SUPERMEMORY_API_KEY", "")
SUPERMEMORY_BASE_URL = os.getenv("SUPERMEMORY_BASE_URL", "https://api.supermemory.ai/v1")
SUPERMEMORY_CONTAINER = os.getenv("SUPERMEMORY_CONTAINER", "decide9ja-prod")


# ===========================================
# DATA CLASSES
# ===========================================

@dataclass
class Memory:
    """A stored memory item."""
    id: str
    content: str
    user_id: str
    metadata: Dict[str, Any]
    created_at: str
    score: float = 0.0  # Relevance score from search


@dataclass
class UserProfile:
    """Auto-generated user profile from memories."""
    user_id: str
    static_facts: List[str]  # Always-true facts (location, preferences)
    dynamic_facts: List[str]  # Recent context (last topics, current interests)
    summary: str
    memory_count: int
    last_interaction: str


# ===========================================
# SUPERMEMORY CLIENT
# ===========================================

class SuperMemoryClient:
    """
    Production Supermemory client for Decide9ja.

    Features:
    - Persistent memory storage across sessions
    - Semantic search with sub-300ms recall
    - Automatic user profiling
    - Memory containerization for multi-tenant safety
    - Feedback loop for continuous learning
    """

    def __init__(self, api_key: str = None, container: str = None):
        self.api_key = api_key or SUPERMEMORY_API_KEY
        self.base_url = SUPERMEMORY_BASE_URL
        self.container = container or SUPERMEMORY_CONTAINER

        if not self.api_key:
            logger.warning("SUPERMEMORY_API_KEY not set - memory features disabled")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Container": self.container,
            },
            timeout=30.0
        )

        self._enabled = bool(self.api_key)
    
    # ===========================================
    # MEMORY OPERATIONS
    # ===========================================

    async def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        memory_type: str = "conversation"
    ) -> Optional[str]:
        """
        Add a memory to Supermemory.

        Args:
            user_id: User identifier (phone hash)
            content: Memory content (conversation, fact, preference)
            metadata: Additional context (intent, entities, location)
            memory_type: Type of memory (conversation, fact, preference, feedback)

        Returns:
            Memory ID if successful, None otherwise
        """
        if not self._enabled:
            return None

        try:
            payload = {
                "content": content,
                "userId": user_id,
                "tags": [self.container, memory_type, f"user:{user_id}"],
                "metadata": {
                    "type": memory_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "decide9ja",
                    **(metadata or {})
                }
            }

            response = await self.client.post("/memories", json=payload)

            if response.status_code in [200, 201]:
                result = response.json()
                memory_id = result.get("id") or result.get("memoryId")
                logger.info(f"Stored memory for user {user_id[:8]}...: {memory_id}")
                return memory_id
            else:
                logger.error(f"Failed to store memory: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Supermemory add error: {e}")
            return None

    async def store_interaction(
        self,
        phone: str,
        user_message: str,
        agent_response: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Store a conversation interaction.
        Convenience method for typical Q&A storage.

        Args:
            phone: User's phone hash
            user_message: What user said
            agent_response: What Tade/agent replied
            metadata: Additional context (intent, entities, location)
        """
        content = f"""User: {user_message}

Agent: {agent_response}"""

        memory_id = await self.add_memory(
            user_id=phone,
            content=content,
            metadata={
                "user_message": user_message[:500],
                "agent_response": agent_response[:500],
                **(metadata or {})
            },
            memory_type="conversation"
        )
        return memory_id is not None
    
    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_types: List[str] = None
    ) -> List[Memory]:
        """
        Search memories semantically for a user.

        Args:
            user_id: User identifier
            query: Search query (semantic)
            limit: Max results to return
            memory_types: Filter by memory types (conversation, fact, preference)

        Returns:
            List of Memory objects with relevance scores
        """
        if not self._enabled:
            return []

        try:
            payload = {
                "query": query,
                "userId": user_id,
                "limit": limit,
                "tags": [self.container, f"user:{user_id}"]
            }

            if memory_types:
                payload["tags"].extend(memory_types)

            response = await self.client.post("/search", json=payload)

            if response.status_code == 200:
                results = response.json()
                memories = []

                for item in results.get("memories", results.get("results", [])):
                    memories.append(Memory(
                        id=item.get("id", ""),
                        content=item.get("content", ""),
                        user_id=user_id,
                        metadata=item.get("metadata", {}),
                        created_at=item.get("createdAt", ""),
                        score=item.get("score", item.get("similarity", 0.0))
                    ))

                logger.info(f"Recalled {len(memories)} memories for user {user_id[:8]}...")
                return memories
            else:
                logger.error(f"Memory search failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Supermemory search error: {e}")
            return []

    async def recall_context(
        self,
        phone: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant context for a user query.
        Legacy compatibility method.
        """
        memories = await self.search_memories(phone, query, limit)
        return [asdict(m) for m in memories]
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get auto-generated user profile from Supermemory.

        Supermemory builds profiles automatically from stored memories,
        extracting static facts (location, preferences) and dynamic
        context (recent topics, current interests).
        """
        if not self._enabled:
            return None

        try:
            response = await self.client.get(
                f"/users/{user_id}/profile",
                params={"container": self.container}
            )

            if response.status_code == 200:
                data = response.json()
                return UserProfile(
                    user_id=user_id,
                    static_facts=data.get("staticFacts", data.get("static_facts", [])),
                    dynamic_facts=data.get("dynamicFacts", data.get("dynamic_facts", [])),
                    summary=data.get("summary", ""),
                    memory_count=data.get("memoryCount", data.get("memory_count", 0)),
                    last_interaction=data.get("lastInteraction", data.get("last_interaction", ""))
                )
            else:
                logger.warning(f"Profile not found for user {user_id[:8]}...")
                return None

        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
            return None
    
    async def store_user_fact(
        self,
        user_id: str,
        fact: str,
        fact_type: str = "preference"
    ) -> bool:
        """
        Store a specific fact about a user.

        Facts are used to build the user profile automatically.
        Types: location, preference, interest, demographic

        Examples:
        - "User lives in Lagos State" (location)
        - "User interested in education budgets" (interest)
        - "User prefers Pidgin responses" (preference)
        - "User is a first-time voter" (demographic)
        """
        memory_id = await self.add_memory(
            user_id=user_id,
            content=fact,
            metadata={"fact_type": fact_type},
            memory_type="fact"
        )
        return memory_id is not None

    # ===========================================
    # FEEDBACK & LEARNING
    # ===========================================

    async def store_feedback(
        self,
        user_id: str,
        query: str,
        response: str,
        feedback_type: str,
        correction: str = None,
        rating: int = None
    ) -> bool:
        """
        Store user feedback for continuous learning.

        Args:
            user_id: User identifier
            query: Original query
            response: Agent's response
            feedback_type: positive, negative, correction, clarification
            correction: User's corrected answer (if feedback_type=correction)
            rating: 1-5 rating (if provided)
        """
        content = f"""FEEDBACK ({feedback_type})
Query: {query}
Response: {response}
{f'Correction: {correction}' if correction else ''}
{f'Rating: {rating}/5' if rating else ''}"""

        metadata = {
            "feedback_type": feedback_type,
            "query": query[:500],
            "response": response[:500],
        }
        if correction:
            metadata["correction"] = correction
        if rating:
            metadata["rating"] = rating

        memory_id = await self.add_memory(
            user_id=user_id,
            content=content,
            metadata=metadata,
            memory_type="feedback"
        )
        return memory_id is not None

    async def get_similar_questions(
        self,
        query: str,
        limit: int = 3
    ) -> List[Memory]:
        """
        Find similar questions asked by any user.
        Useful for learning common query patterns.
        """
        if not self._enabled:
            return []

        try:
            payload = {
                "query": query,
                "limit": limit,
                "tags": [self.container, "conversation"]
            }

            response = await self.client.post("/search", json=payload)

            if response.status_code == 200:
                results = response.json()
                return [
                    Memory(
                        id=item.get("id", ""),
                        content=item.get("content", ""),
                        user_id=item.get("userId", ""),
                        metadata=item.get("metadata", {}),
                        created_at=item.get("createdAt", ""),
                        score=item.get("score", 0.0)
                    )
                    for item in results.get("memories", results.get("results", []))
                ]
            return []

        except Exception as e:
            logger.error(f"Similar questions search error: {e}")
            return []
    
    async def get_conversation_summary(
        self,
        user_id: str,
        limit: int = 10
    ) -> str:
        """
        Get a summary of recent conversations with a user.
        Useful for context compression and session recovery.
        """
        memories = await self.search_memories(
            user_id=user_id,
            query="recent conversation topics and questions",
            limit=limit,
            memory_types=["conversation"]
        )

        if not memories:
            return ""

        # Extract key topics
        topics = []
        for mem in memories:
            content = mem.content
            # Extract user question from conversation format
            if "User:" in content:
                user_part = content.split("User:")[1].split("Agent:")[0].strip()
                if user_part:
                    topics.append(user_part[:100])

        if topics:
            return "Recent topics: " + "; ".join(topics[-5:])

        return ""

    async def delete_user_memories(self, user_id: str) -> bool:
        """
        Delete all memories for a user (GDPR compliance).
        """
        if not self._enabled:
            return True

        try:
            response = await self.client.delete(
                f"/users/{user_id}/memories",
                params={"container": self.container}
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Delete user memories error: {e}")
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ===========================================
# LEGACY COMPATIBILITY - TadeSupermemory alias
# ===========================================

# Alias for backwards compatibility with existing code
TadeSupermemory = SuperMemoryClient


# ===========================================
# HELPER FUNCTIONS FOR MESSAGE HANDLER
# ===========================================

async def enhance_with_supermemory(
    phone: str,
    user_message: str,
    agent_response: str,
    metadata: Dict[str, Any] = None
):
    """
    Store interaction in SuperMemory after response generation.

    Usage in message_handler_v5.py:
        await enhance_with_supermemory(phone, text, response, {
            "intent": intent,
            "entities": entities,
            "location": user_state
        })
    """
    async with SuperMemoryClient() as memory:
        # Store the interaction
        await memory.store_interaction(phone, user_message, agent_response, metadata)

        # Extract and store facts from metadata
        if metadata:
            if metadata.get("location"):
                await memory.store_user_fact(
                    phone,
                    f"User is located in {metadata['location']}",
                    "location"
                )

            if metadata.get("interests"):
                for interest in metadata["interests"]:
                    await memory.store_user_fact(
                        phone,
                        f"User interested in {interest}",
                        "interest"
                    )

            if metadata.get("state"):
                await memory.store_user_fact(
                    phone,
                    f"User is in {metadata['state']} state",
                    "location"
                )


# Alias for backwards compatibility
enhance_tade_with_supermemory = enhance_with_supermemory


async def get_memory_context(phone: str, query: str) -> str:
    """
    Get relevant context from SuperMemory before generating response.

    Usage in message_handler_v5.py:
        context = await get_memory_context(phone, user_message)
        # Add to Claude prompt
    """
    async with SuperMemoryClient() as memory:
        memories = await memory.search_memories(phone, query, limit=3)

        if not memories:
            return ""

        # Format for Claude prompt
        context_parts = []
        for mem in memories:
            # Extract previous agent responses
            if "Agent:" in mem.content:
                agent_part = mem.content.split("Agent:")[1].strip()
                context_parts.append(f"- {agent_part[:200]}")

        if context_parts:
            return "Previous relevant context:\n" + "\n".join(context_parts)

        return ""


# Alias for backwards compatibility
get_supermemory_context = get_memory_context


async def get_user_memory_profile(phone: str) -> Dict[str, Any]:
    """
    Get user profile with facts and recent context.

    Returns dict with:
    - static_facts: Location, preferences that don't change
    - dynamic_facts: Recent topics, current interests
    - summary: Brief user description
    """
    async with SuperMemoryClient() as memory:
        profile = await memory.get_user_profile(phone)

        if profile:
            return {
                "static_facts": profile.static_facts,
                "dynamic_facts": profile.dynamic_facts,
                "summary": profile.summary,
                "memory_count": profile.memory_count
            }

        return {
            "static_facts": [],
            "dynamic_facts": [],
            "summary": "New user",
            "memory_count": 0
        }


async def migrate_user_to_supermemory(phone: str, user_state: Any, history: List[Dict]):
    """
    Migrate existing user data to SuperMemory.
    Run once per user on first interaction after deployment.
    """
    async with SuperMemoryClient() as memory:
        # Store user facts
        if hasattr(user_state, 'state') and user_state.state:
            await memory.store_user_fact(phone, f"User is in {user_state.state} state", "location")

        if hasattr(user_state, 'lga') and user_state.lga:
            await memory.store_user_fact(phone, f"User's LGA is {user_state.lga}", "location")

        if hasattr(user_state, 'interests') and user_state.interests:
            for interest in user_state.interests:
                await memory.store_user_fact(phone, f"User interested in {interest}", "interest")

        # Migrate recent history
        for msg in history[-10:]:
            if msg.get("role") == "user":
                await memory.add_memory(
                    user_id=phone,
                    content=f"User: {msg.get('content', '')}",
                    metadata={"migrated": True, "original_timestamp": msg.get("timestamp")},
                    memory_type="conversation"
                )

        logger.info(f"Migrated user {phone[:8]}... to SuperMemory")


# ===========================================
# METRICS & MONITORING
# ===========================================

class SuperMemoryMetrics:
    """Track SuperMemory usage and effectiveness."""

    def __init__(self):
        self.stats = {
            "stores": 0,
            "searches": 0,
            "avg_relevance": 0.0,
            "profile_fetches": 0,
            "feedback_stored": 0,
            "errors": 0
        }

    def record_store(self):
        self.stats["stores"] += 1

    def record_search(self, relevance_score: float):
        self.stats["searches"] += 1
        n = self.stats["searches"]
        self.stats["avg_relevance"] = (
            (self.stats["avg_relevance"] * (n - 1) + relevance_score) / n
        )

    def record_feedback(self):
        self.stats["feedback_stored"] += 1

    def record_error(self):
        self.stats["errors"] += 1

    def get_report(self) -> Dict:
        return {
            **self.stats,
            "effectiveness_score": self.stats["avg_relevance"],
            "error_rate": self.stats["errors"] / max(1, self.stats["stores"] + self.stats["searches"])
        }


# Alias for backwards compatibility
SupermemoryMetrics = SuperMemoryMetrics
