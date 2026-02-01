"""
Supermemory Integration for Decide9ja (Old Tade)

Replaces custom memory with Supermemory for:
- Cross-session persistence
- Automatic user profiling
- Semantic recall
- 1-month learning period before building our own

Usage:
    from supermemory_integration import TadeSupermemory
    
    memory = TadeSupermemory()
    await memory.store_interaction(phone, message, response)
    context = await memory.recall_context(phone, query)
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Supermemory client (using their API directly)
import httpx

logger = logging.getLogger(__name__)

SUPERMEMORY_API_KEY = os.getenv("SUPERMEMORY_API_KEY", "sm_2YjQGcbZqBgtUhQuJZmGur_jjJBWVrjxCusomPYZOiEPyphQmUPsJINLyqijzoaUoDGrqUnttcQyOOmDjuMEBtk")
SUPERMEMORY_BASE_URL = "https://api.supermemory.ai/v1"


class TadeSupermemory:
    """
    Supermemory integration for Tade/Decide9ja.
    
    Provides:
    - Automatic conversation storage
    - Semantic search across history
    - User profile building
    - Cross-session continuity
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or SUPERMEMORY_API_KEY
        self.base_url = SUPERMEMORY_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        
        # Container tag for Tade memories
        self.container = "tade-decide9ja"
    
    async def store_interaction(
        self,
        phone: str,
        user_message: str,
        tade_response: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Store a conversation interaction in Supermemory.
        
        Args:
            phone: User's phone number (hashed for privacy)
            user_message: What user said
            tade_response: What Tade replied
            metadata: Additional context (location, query type, etc.)
        """
        try:
            # Create memory content
            content = f"""User ({phone}): {user_message}

Tade: {tade_response}

Context: {json.dumps(metadata) if metadata else "None"}"""
            
            # Store in Supermemory
            response = await self.client.post(
                "/memories",
                json={
                    "content": content,
                    "tags": [self.container, f"user:{phone}", "conversation"],
                    "metadata": {
                        "phone": phone,
                        "timestamp": datetime.utcnow().isoformat(),
                        **(metadata or {})
                    }
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Stored interaction for {phone}")
                return True
            else:
                logger.error(f"Failed to store: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Supermemory store error: {e}")
            return False
    
    async def recall_context(
        self,
        phone: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant context for a user query.
        
        Args:
            phone: User's phone number
            query: Current query to find context for
            limit: Max memories to return
            
        Returns:
            List of relevant memories with similarity scores
        """
        try:
            # Search Supermemory
            response = await self.client.post(
                "/search",
                json={
                    "query": query,
                    "tags": [self.container, f"user:{phone}"],
                    "limit": limit
                }
            )
            
            if response.status_code == 200:
                results = response.json()
                logger.info(f"Recalled {len(results.get('memories', []))} memories for {phone}")
                return results.get("memories", [])
            else:
                logger.error(f"Failed to recall: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Supermemory recall error: {e}")
            return []
    
    async def get_user_profile(self, phone: str) -> Dict[str, Any]:
        """
        Get auto-generated user profile from Supermemory.
        
        Supermemory builds profiles automatically from stored memories.
        """
        try:
            response = await self.client.get(
                f"/profiles/{phone}",
                params={"container": self.container}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
            return {}
    
    async def store_user_fact(
        self,
        phone: str,
        fact: str,
        fact_type: str = "preference"
    ) -> bool:
        """
        Store a specific fact about a user.
        
        Examples:
        - "User lives in Lagos State"
        - "User interested in education budgets"
        - "User prefers Pidgin responses"
        """
        try:
            response = await self.client.post(
                "/memories",
                json={
                    "content": fact,
                    "tags": [self.container, f"user:{phone}", "fact", fact_type],
                    "metadata": {
                        "phone": phone,
                        "fact_type": fact_type,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Fact store error: {e}")
            return False
    
    async def get_conversation_summary(
        self,
        phone: str,
        since: datetime = None
    ) -> str:
        """
        Get a summary of recent conversations with a user.
        
        Useful for context compression recovery.
        """
        try:
            # Get recent memories
            memories = await self.recall_context(
                phone=phone,
                query="recent conversation summary",
                limit=10
            )
            
            if not memories:
                return ""
            
            # Extract key points
            key_points = []
            for mem in memories:
                content = mem.get("content", "")
                # Extract just the user messages for summary
                if "User (" in content:
                    user_msg = content.split("User (")[1].split("):")[1].split("\n\nTade:")[0].strip()
                    key_points.append(user_msg)
            
            if key_points:
                return "Previous topics: " + "; ".join(key_points[-5:])
            
            return ""
            
        except Exception as e:
            logger.error(f"Summary error: {e}")
            return ""
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Integration helper for message_handler_v4.py
async def enhance_tade_with_supermemory(
    phone: str,
    user_message: str,
    tade_response: str,
    metadata: Dict[str, Any] = None
):
    """
    Drop-in replacement for existing memory storage.
    
    Usage in message_handler_v4.py:
        # OLD (custom memory):
        # user_memory.save_message(phone, "user", text)
        
        # NEW (Supermemory):
        await enhance_tade_with_supermemory(phone, text, response, {
            "location": user_state.state,
            "query_type": intent
        })
    """
    memory = TadeSupermemory()
    
    try:
        # Store interaction
        await memory.store_interaction(phone, user_message, tade_response, metadata)
        
        # If location collected, store as fact
        if metadata and metadata.get("location"):
            await memory.store_user_fact(
                phone,
                f"User is located in {metadata['location']}",
                "location"
            )
        
        # If interests mentioned, store as fact
        if metadata and metadata.get("interests"):
            for interest in metadata["interests"]:
                await memory.store_user_fact(
                    phone,
                    f"User interested in {interest}",
                    "interest"
                )
                
    finally:
        await memory.close()


async def get_supermemory_context(phone: str, query: str) -> str:
    """
    Get relevant context from Supermemory before generating response.
    
    Usage in message_handler_v4.py:
        # Before calling Claude:
        context = await get_supermemory_context(phone, user_message)
        # Add context to Claude prompt
    """
    memory = TadeSupermemory()
    
    try:
        # Recall relevant memories
        memories = await memory.recall_context(phone, query, limit=3)
        
        if not memories:
            return ""
        
        # Format for Claude prompt
        context_parts = []
        for mem in memories:
            content = mem.get("content", "")
            # Extract relevant parts
            if "Tade:" in content:
                # Previous Q&A
                context_parts.append(content.split("Tade:")[1].split("\n\nContext:")[0].strip())
        
        if context_parts:
            return "Relevant previous context:\n" + "\n".join(context_parts)
        
        return ""
        
    finally:
        await memory.close()


# Migration script from old memory to Supermemory
async def migrate_user_to_supermemory(phone: str, user_state: Any, history: List[Dict]):
    """
    Migrate existing user data to Supermemory.
    
    Run once per user on first interaction after Supermemory deployment.
    """
    memory = TadeSupermemory()
    
    try:
        # Store user facts
        if user_state.state:
            await memory.store_user_fact(phone, f"User is in {user_state.state} state", "location")
        
        if user_state.lga:
            await memory.store_user_fact(phone, f"User's LGA is {user_state.lga}", "location")
        
        if user_state.interests:
            for interest in user_state.interests:
                await memory.store_user_fact(phone, f"User interested in {interest}", "interest")
        
        # Migrate recent history (last 10 messages)
        for msg in history[-10:]:
            if msg.get("role") in ["user", "assistant"]:
                await memory.store_interaction(
                    phone=phone,
                    user_message=msg.get("content", ""),
                    tade_response="",  # We don't have the response in old format
                    metadata={"migrated": True, "original_timestamp": msg.get("timestamp")}
                )
        
        logger.info(f"Migrated user {phone} to Supermemory")
        
    finally:
        await memory.close()


# Monitoring/metrics for the 1-month learning period
class SupermemoryMetrics:
    """Track Supermemory usage and effectiveness during learning period"""
    
    def __init__(self):
        self.stats = {
            "stores": 0,
            "recalls": 0,
            "avg_recall_relevance": 0.0,
            "profile_hits": 0
        }
    
    def record_store(self):
        self.stats["stores"] += 1
    
    def record_recall(self, relevance_score: float):
        self.stats["recalls"] += 1
        # Update running average
        n = self.stats["recalls"]
        self.stats["avg_recall_relevance"] = (
            (self.stats["avg_recall_relevance"] * (n - 1) + relevance_score) / n
        )
    
    def get_report(self) -> Dict:
        return {
            **self.stats,
            "effectiveness_score": self.stats["avg_recall_relevance"],
            "recommendation": self._get_recommendation()
        }
    
    def _get_recommendation(self) -> str:
        """Generate recommendation for building our own system"""
        if self.stats["avg_recall_relevance"] > 0.8:
            return "High effectiveness. Consider building similar semantic search system."
        elif self.stats["avg_recall_relevance"] > 0.6:
            return "Moderate effectiveness. May need hybrid approach."
        else:
            return "Low effectiveness. Consider different memory architecture."
