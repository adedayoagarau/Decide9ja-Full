"""
Enhanced Memory System for Decide9ja/Tade Chatbot.

Implements three key memory improvements based on AI agent memory research:
1. Episodic Memory Enhancement - Conversation summarization & key fact extraction
2. Vector Search on User History - Semantic retrieval of past conversations
3. User Profile Building - LLM-powered inference of preferences/interests

References:
- MemGPT: Cognitive triage for memory importance evaluation
- Mem0: Dual-memory approach with session summaries + long-term retrieval
- IMPChat: Implicit user profile learning from dialogue history

Author: Decide9ja Team
"""
import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from app.database import SessionLocal, ChatHistory, User
from app.services.embeddings import get_embedding, get_embeddings, cosine_similarity

# Import memory prompts from federated prompt system
from app.services.prompts import (
    build_episode_summary_prompt,
    build_fact_extraction_prompt,
    build_personalization_prompt
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MemoryFact:
    """A single extracted fact about the user."""
    fact_type: str  # preference, interest, demographic, opinion, concern
    content: str
    confidence: float  # 0-1
    source_turn: int  # Which conversation turn this came from
    extracted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConversationEpisode:
    """A summarized conversation session (episodic memory)."""
    session_id: str
    summary: str
    key_facts: List[MemoryFact]
    topics_discussed: List[str]
    sentiment: str  # positive, neutral, negative, mixed
    turn_count: int
    started_at: datetime
    ended_at: datetime
    importance_score: float  # 0-1, for memory prioritization


@dataclass
class UserProfile:
    """Comprehensive user profile built from conversation history."""
    # Demographics (explicit)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None

    # Inferred interests (from conversations)
    political_interests: List[str] = field(default_factory=list)
    topic_preferences: Dict[str, float] = field(default_factory=dict)  # topic -> engagement score

    # Political stance indicators (inferred, never explicit)
    parties_discussed: Dict[str, int] = field(default_factory=dict)  # party -> mention count
    politicians_followed: List[str] = field(default_factory=list)

    # Communication style
    preferred_language: str = "english"  # english, pidgin, mixed
    formality_level: str = "casual"  # formal, casual, mixed
    avg_message_length: float = 0
    asks_follow_ups: bool = False

    # Concerns & priorities
    top_concerns: List[str] = field(default_factory=list)  # security, economy, education, etc.
    local_issues_mentioned: List[str] = field(default_factory=list)

    # Engagement patterns
    total_sessions: int = 0
    total_messages: int = 0
    avg_session_length: float = 0
    most_active_time: Optional[str] = None  # morning, afternoon, evening

    # Memory metadata
    last_profile_update: datetime = field(default_factory=datetime.utcnow)
    profile_confidence: float = 0.0  # 0-1


# =============================================================================
# ENHANCED MEMORY SERVICE
# =============================================================================

class EnhancedMemoryService:
    """
    Advanced memory system for Tade chatbot.

    Features:
    - Episodic memory: Summarizes and stores conversation sessions
    - Semantic memory: Embeds conversations for vector search
    - Profile building: Infers user preferences from dialogue
    """

    def __init__(self):
        self.embedding_dim = 1536  # OpenAI text-embedding-3-small
        self.max_context_messages = 10
        self.summary_threshold = 6  # Summarize after N turns

    def _hash_phone(self, phone: str) -> str:
        """Hash phone number for privacy."""
        clean_phone = phone.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        return hashlib.sha256(clean_phone.encode()).hexdigest()

    # =========================================================================
    # EPISODIC MEMORY - Conversation Summarization
    # =========================================================================

    async def create_episode_summary(
        self,
        phone: str,
        conversation: List[Dict[str, str]],
        session_id: str = None
    ) -> ConversationEpisode:
        """
        Create an episodic memory from a conversation session.
        Uses LLM to summarize and extract key facts (cognitive triage).

        Args:
            phone: User's phone number
            conversation: List of {role, content} messages
            session_id: Optional session identifier

        Returns:
            ConversationEpisode with summary and extracted facts
        """
        import anthropic

        if not conversation:
            return None

        session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Build prompt using federated prompt system
        prompt = build_episode_summary_prompt(conversation)

        try:
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            result = json.loads(result_text)

            # Build episode
            key_facts = [
                MemoryFact(
                    fact_type=f.get("type", "interest"),
                    content=f.get("content", ""),
                    confidence=f.get("confidence", 0.5),
                    source_turn=len(conversation)
                )
                for f in result.get("key_facts", [])
            ]

            episode = ConversationEpisode(
                session_id=session_id,
                summary=result.get("summary", ""),
                key_facts=key_facts,
                topics_discussed=result.get("topics", []),
                sentiment=result.get("sentiment", "neutral"),
                turn_count=len(conversation),
                started_at=datetime.utcnow() - timedelta(minutes=len(conversation) * 2),
                ended_at=datetime.utcnow(),
                importance_score=result.get("importance", 0.5)
            )

            # Store episode in database
            await self._store_episode(phone, episode)

            logger.info(f"Created episode for user: {len(key_facts)} facts, importance={episode.importance_score}")
            return episode

        except Exception as e:
            logger.error(f"Episode creation error: {e}")
            # Return basic episode without LLM analysis
            return ConversationEpisode(
                session_id=session_id,
                summary="Conversation with user",
                key_facts=[],
                topics_discussed=[],
                sentiment="neutral",
                turn_count=len(conversation),
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                importance_score=0.3
            )

    async def _store_episode(self, phone: str, episode: ConversationEpisode):
        """Store episode in database."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if user:
                # Store in preferences_json
                prefs = {}
                if user.preferences_json:
                    try:
                        prefs = json.loads(user.preferences_json)
                    except:
                        prefs = {}

                # Add to episodes list
                episodes = prefs.get("episodes", [])
                episodes.append({
                    "session_id": episode.session_id,
                    "summary": episode.summary,
                    "key_facts": [
                        {"type": f.fact_type, "content": f.content, "confidence": f.confidence}
                        for f in episode.key_facts
                    ],
                    "topics": episode.topics_discussed,
                    "sentiment": episode.sentiment,
                    "importance": episode.importance_score,
                    "created_at": datetime.utcnow().isoformat()
                })

                # Keep only last 20 episodes
                episodes = episodes[-20:]
                prefs["episodes"] = episodes

                user.preferences_json = json.dumps(prefs)
                db.commit()

        except Exception as e:
            logger.error(f"Store episode error: {e}")
            db.rollback()
        finally:
            db.close()

    def get_recent_episodes(self, phone: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation episodes for a user."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if user and user.preferences_json:
                prefs = json.loads(user.preferences_json)
                episodes = prefs.get("episodes", [])
                return episodes[-limit:]
            return []

        except Exception as e:
            logger.error(f"Get episodes error: {e}")
            return []
        finally:
            db.close()

    # =========================================================================
    # VECTOR SEARCH - Semantic Memory Retrieval
    # =========================================================================

    async def embed_and_store_message(
        self,
        phone: str,
        role: str,
        content: str,
        metadata: Dict = None
    ):
        """
        Embed a message and store for semantic search.

        Args:
            phone: User's phone number
            role: 'user' or 'assistant'
            content: Message content
            metadata: Optional metadata (intent, topic, etc.)
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Generate embedding
            embedding = get_embedding(content[:2000])  # Truncate long messages

            # Store in chat_history with embedding
            # Note: For production, use pgvector or dedicated vector DB
            chat_entry = ChatHistory(
                phone_hash=user_hash,
                role=role,
                content=content[:4000],
                timestamp=datetime.utcnow(),
                intent=metadata.get("intent", "unknown") if metadata else "unknown"
            )

            db.add(chat_entry)
            db.commit()

            # Store embedding separately (in user preferences for now)
            # In production, use a proper vector database
            await self._store_embedding(user_hash, chat_entry.id, embedding, content[:200])

        except Exception as e:
            logger.error(f"Embed message error: {e}")
            db.rollback()
        finally:
            db.close()

    async def _store_embedding(
        self,
        user_hash: str,
        message_id: int,
        embedding: List[float],
        preview: str
    ):
        """Store message embedding for vector search."""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if user:
                prefs = {}
                if user.preferences_json:
                    try:
                        prefs = json.loads(user.preferences_json)
                    except:
                        prefs = {}

                # Store embeddings (keep last 100)
                embeddings = prefs.get("message_embeddings", [])
                embeddings.append({
                    "id": message_id,
                    "embedding": embedding[:100],  # Store truncated for space
                    "preview": preview,
                    "timestamp": datetime.utcnow().isoformat()
                })
                embeddings = embeddings[-100:]
                prefs["message_embeddings"] = embeddings

                user.preferences_json = json.dumps(prefs)
                db.commit()

        except Exception as e:
            logger.error(f"Store embedding error: {e}")
            db.rollback()
        finally:
            db.close()

    def semantic_search_history(
        self,
        phone: str,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search user's conversation history semantically.

        Args:
            phone: User's phone number
            query: Search query
            limit: Max results to return

        Returns:
            List of relevant past messages with similarity scores
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Get query embedding
            query_embedding = get_embedding(query)

            # Get user's stored embeddings
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user or not user.preferences_json:
                return []

            prefs = json.loads(user.preferences_json)
            stored_embeddings = prefs.get("message_embeddings", [])

            if not stored_embeddings:
                return []

            # Calculate similarities
            results = []
            for item in stored_embeddings:
                # Pad truncated embedding for comparison
                stored_emb = item["embedding"]
                if len(stored_emb) < len(query_embedding):
                    stored_emb = stored_emb + [0.0] * (len(query_embedding) - len(stored_emb))

                similarity = cosine_similarity(query_embedding, stored_emb)
                results.append({
                    "id": item["id"],
                    "preview": item["preview"],
                    "timestamp": item["timestamp"],
                    "similarity": similarity
                })

            # Sort by similarity and return top results
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
        finally:
            db.close()

    def get_relevant_context(
        self,
        phone: str,
        current_query: str,
        max_context: int = 5
    ) -> str:
        """
        Get relevant past context for the current query.
        Combines recent history + semantically similar past conversations.

        Args:
            phone: User's phone number
            current_query: Current user message
            max_context: Max past messages to include

        Returns:
            Formatted context string for LLM
        """
        # Semantic search for relevant past messages
        relevant = self.semantic_search_history(phone, current_query, limit=3)

        # Get recent episodes
        episodes = self.get_recent_episodes(phone, limit=2)

        context_parts = []

        # Add episode summaries if available
        if episodes:
            context_parts.append("PAST CONVERSATION SUMMARIES:")
            for ep in episodes:
                context_parts.append(f"- {ep.get('summary', '')}")
                if ep.get('key_facts'):
                    for fact in ep['key_facts'][:2]:
                        context_parts.append(f"  • {fact.get('content', '')}")

        # Add semantically relevant past messages
        if relevant:
            context_parts.append("\nRELATED PAST MESSAGES:")
            for item in relevant:
                if item["similarity"] > 0.3:  # Only include if reasonably similar
                    context_parts.append(f"- [{item['timestamp'][:10]}] {item['preview']}")

        return "\n".join(context_parts) if context_parts else ""

    # =========================================================================
    # USER PROFILE BUILDING - Preference Inference
    # =========================================================================

    async def build_user_profile(
        self,
        phone: str,
        conversation_history: List[Dict] = None
    ) -> UserProfile:
        """
        Build/update comprehensive user profile from conversation history.
        Uses LLM to infer preferences, interests, and communication style.

        Args:
            phone: User's phone number
            conversation_history: Recent conversation (optional, fetches if not provided)

        Returns:
            Updated UserProfile
        """
        import anthropic

        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            # Get existing profile
            profile = UserProfile()
            if user:
                profile.first_name = getattr(user, 'first_name', None)
                profile.last_name = getattr(user, 'last_name', None)
                profile.state = user.state
                profile.lga = user.lga

            # Get conversation history if not provided
            if not conversation_history:
                history = db.query(ChatHistory).filter(
                    ChatHistory.phone_hash == user_hash
                ).order_by(ChatHistory.timestamp.desc()).limit(50).all()

                conversation_history = [
                    {"role": h.role, "content": h.content}
                    for h in reversed(history)
                ]

            if len(conversation_history) < 5:
                # Not enough data to build profile
                return profile

            # Use LLM to analyze conversation patterns
            conv_text = "\n".join([
                f"{'User' if m['role'] == 'user' else 'Tade'}: {m['content'][:200]}"
                for m in conversation_history[-30:]  # Last 30 messages
            ])

            prompt = f"""Analyze this conversation history and extract user profile information:

Conversation:
{conv_text}

Extract the following (only include if clearly evident):
1. Political interests (elections, specific politicians, parties, policies)
2. Top concerns (security, economy, education, healthcare, infrastructure)
3. Communication style (formal/casual, uses Pidgin, message length)
4. Topics they engage with most
5. Any local issues they've mentioned
6. Politicians or parties they discuss (neutral - just tracking, not inferring support)

Respond in JSON:
{{
    "political_interests": ["interest1", "interest2"],
    "top_concerns": ["concern1", "concern2"],
    "communication_style": {{
        "language": "english|pidgin|mixed",
        "formality": "formal|casual|mixed",
        "asks_followups": true|false
    }},
    "engaged_topics": {{"topic": score_0_to_1}},
    "local_issues": ["issue1"],
    "parties_discussed": {{"party": mention_count}},
    "politicians_discussed": ["name1", "name2"]
}}

Be conservative - only include what's clearly evident from the conversation."""

            try:
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}]
                )

                result_text = response.content[0].text.strip()

                # Parse JSON
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]

                result = json.loads(result_text)

                # Update profile
                profile.political_interests = result.get("political_interests", [])
                profile.top_concerns = result.get("top_concerns", [])
                profile.topic_preferences = result.get("engaged_topics", {})
                profile.local_issues_mentioned = result.get("local_issues", [])
                profile.parties_discussed = result.get("parties_discussed", {})
                profile.politicians_followed = result.get("politicians_discussed", [])

                style = result.get("communication_style", {})
                profile.preferred_language = style.get("language", "english")
                profile.formality_level = style.get("formality", "casual")
                profile.asks_follow_ups = style.get("asks_followups", False)

                # Calculate engagement stats
                profile.total_messages = len(conversation_history)
                user_messages = [m for m in conversation_history if m["role"] == "user"]
                if user_messages:
                    profile.avg_message_length = sum(len(m["content"]) for m in user_messages) / len(user_messages)

                profile.last_profile_update = datetime.utcnow()
                profile.profile_confidence = min(0.9, len(conversation_history) / 100)

                # Store profile
                await self._store_profile(user_hash, profile)

                logger.info(f"Built profile: {len(profile.political_interests)} interests, {len(profile.top_concerns)} concerns")
                return profile

            except Exception as e:
                logger.error(f"Profile LLM error: {e}")
                return profile

        except Exception as e:
            logger.error(f"Build profile error: {e}")
            return UserProfile()
        finally:
            db.close()

    async def _store_profile(self, user_hash: str, profile: UserProfile):
        """Store user profile in database."""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if user:
                prefs = {}
                if user.preferences_json:
                    try:
                        prefs = json.loads(user.preferences_json)
                    except:
                        prefs = {}

                # Store profile
                prefs["inferred_profile"] = {
                    "political_interests": profile.political_interests,
                    "top_concerns": profile.top_concerns,
                    "topic_preferences": profile.topic_preferences,
                    "communication_style": {
                        "language": profile.preferred_language,
                        "formality": profile.formality_level,
                        "asks_followups": profile.asks_follow_ups
                    },
                    "local_issues": profile.local_issues_mentioned,
                    "parties_discussed": profile.parties_discussed,
                    "politicians_followed": profile.politicians_followed,
                    "total_messages": profile.total_messages,
                    "avg_message_length": profile.avg_message_length,
                    "profile_confidence": profile.profile_confidence,
                    "last_updated": profile.last_profile_update.isoformat()
                }

                user.preferences_json = json.dumps(prefs)
                db.commit()

        except Exception as e:
            logger.error(f"Store profile error: {e}")
            db.rollback()
        finally:
            db.close()

    def get_user_profile(self, phone: str) -> Optional[Dict]:
        """Get stored user profile."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if user and user.preferences_json:
                prefs = json.loads(user.preferences_json)
                return prefs.get("inferred_profile")
            return None

        except Exception as e:
            logger.error(f"Get profile error: {e}")
            return None
        finally:
            db.close()

    # =========================================================================
    # PERSONALIZATION - Context Building
    # =========================================================================

    def get_personalization_context(self, phone: str) -> str:
        """
        Build personalization context for LLM responses.
        Combines profile insights with relevant past context.

        Args:
            phone: User's phone number

        Returns:
            Formatted personalization context for system prompt
        """
        profile = self.get_user_profile(phone)
        episodes = self.get_recent_episodes(phone, limit=3)

        context_parts = []

        if profile:
            # Add interests
            if profile.get("political_interests"):
                interests = ", ".join(profile["political_interests"][:5])
                context_parts.append(f"User interests: {interests}")

            # Add concerns
            if profile.get("top_concerns"):
                concerns = ", ".join(profile["top_concerns"][:3])
                context_parts.append(f"User concerns: {concerns}")

            # Add communication style
            style = profile.get("communication_style", {})
            if style.get("language") == "pidgin":
                context_parts.append("User prefers Pidgin explanations")
            if style.get("asks_followups"):
                context_parts.append("User often asks follow-up questions")

            # Add local context
            if profile.get("local_issues"):
                context_parts.append(f"Local issues mentioned: {', '.join(profile['local_issues'][:3])}")

        # Add recent conversation context
        if episodes:
            context_parts.append("\nRecent conversation context:")
            for ep in episodes[-2:]:
                if ep.get("summary"):
                    context_parts.append(f"- {ep['summary']}")

        return "\n".join(context_parts) if context_parts else ""

    # =========================================================================
    # MEMORY MAINTENANCE
    # =========================================================================

    async def consolidate_memory(self, phone: str):
        """
        Periodic memory consolidation:
        - Summarize old conversations
        - Update user profile
        - Prune low-importance episodes

        Should be called periodically (e.g., after session ends or daily).
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Get recent conversation for summarization
            history = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).order_by(ChatHistory.timestamp.desc()).limit(20).all()

            if len(history) >= self.summary_threshold:
                # Create episode from recent conversation
                conversation = [
                    {"role": h.role, "content": h.content}
                    for h in reversed(history)
                ]
                await self.create_episode_summary(phone, conversation)

            # Rebuild profile with new data
            await self.build_user_profile(phone)

            logger.info(f"Consolidated memory for user {user_hash[:8]}...")

        except Exception as e:
            logger.error(f"Memory consolidation error: {e}")
        finally:
            db.close()

    def get_memory_stats(self, phone: str) -> Dict:
        """Get memory statistics for a user."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Count messages
            total_messages = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).count()

            # Get profile
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            episodes_count = 0
            embeddings_count = 0
            profile_exists = False

            if user and user.preferences_json:
                prefs = json.loads(user.preferences_json)
                episodes_count = len(prefs.get("episodes", []))
                embeddings_count = len(prefs.get("message_embeddings", []))
                profile_exists = "inferred_profile" in prefs

            return {
                "total_messages": total_messages,
                "episodes_stored": episodes_count,
                "embeddings_stored": embeddings_count,
                "profile_exists": profile_exists,
                "user_hash": user_hash[:8] + "..."
            }

        except Exception as e:
            logger.error(f"Memory stats error: {e}")
            return {}
        finally:
            db.close()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

enhanced_memory = EnhancedMemoryService()
