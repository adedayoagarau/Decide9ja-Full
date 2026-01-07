"""
User Memory Service
Persistent memory storage for each user's conversation history and context.
Enables Tade to remember past conversations and provide continuity.
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from app.database import SessionLocal, ChatHistory, User

logger = logging.getLogger(__name__)


@dataclass
class ConversationMemory:
    """Represents a user's conversation memory bucket."""
    user_hash: str
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None

    # Conversation history (most recent first)
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)

    # Topics and interests extracted from conversations
    topics_discussed: List[str] = field(default_factory=list)
    politicians_asked_about: List[str] = field(default_factory=list)

    # User stats
    total_messages: int = 0
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    session_count: int = 0

    # Flags
    is_returning_user: bool = False
    days_since_last_chat: int = 0


class UserMemoryService:
    """
    Service for managing user conversation memory.
    Each user has a "memory bucket" that persists across sessions.
    """

    def __init__(self):
        self.max_history_messages = 20  # Load last 20 messages for context
        self.context_window = 10  # Use last 10 for Claude context

    def _hash_phone(self, phone: str) -> str:
        """Hash phone number for privacy."""
        clean_phone = phone.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        return hashlib.sha256(clean_phone.encode()).hexdigest()

    def save_message(
        self,
        phone: str,
        role: str,  # 'user' or 'assistant'
        content: str,
        intent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Save a message to the user's conversation history.
        This is the core function that enables memory persistence.
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Create chat history entry
            chat_entry = ChatHistory(
                phone_hash=user_hash,
                role=role,
                content=content[:4000],  # Truncate if too long
                timestamp=datetime.utcnow(),
                intent=intent or "unknown"
            )

            db.add(chat_entry)

            # Update user's last interaction
            user = db.query(User).filter(User.phone_hash == user_hash).first()
            if user:
                user.last_interaction = datetime.utcnow()

            db.commit()
            logger.debug(f"Saved {role} message for user {user_hash[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def get_user_memory(self, phone: str) -> ConversationMemory:
        """
        Load a user's complete memory bucket.
        Called when a user starts a new conversation.
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Get user profile
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            # Get conversation history
            history = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).order_by(ChatHistory.timestamp.desc()).limit(self.max_history_messages).all()

            # Build memory object
            memory = ConversationMemory(user_hash=user_hash)

            if user:
                memory.name = user.name
                memory.state = user.state
                memory.lga = user.lga
                memory.first_interaction = user.created_at
                memory.last_interaction = user.last_interaction

                # Calculate days since last chat
                if user.last_interaction:
                    delta = datetime.utcnow() - user.last_interaction
                    memory.days_since_last_chat = delta.days
                    memory.is_returning_user = delta.days > 0 or delta.seconds > 3600  # > 1 hour

            # Process history
            if history:
                memory.total_messages = len(history)
                memory.recent_messages = [
                    {
                        "role": h.role,
                        "content": h.content,
                        "timestamp": h.timestamp.isoformat() if h.timestamp else None,
                        "intent": h.intent
                    }
                    for h in reversed(history)  # Chronological order
                ]

                # Extract topics and politicians from history
                memory.topics_discussed = self._extract_topics(history)
                memory.politicians_asked_about = self._extract_politicians(history)

            return memory

        except Exception as e:
            logger.error(f"Failed to load user memory: {e}")
            return ConversationMemory(user_hash=self._hash_phone(phone))
        finally:
            db.close()

    def get_conversation_context(self, phone: str, limit: int = None) -> List[Dict]:
        """
        Get recent conversation history formatted for Claude context.
        Returns messages in the format Claude expects.
        """
        limit = limit or self.context_window
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            history = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).order_by(ChatHistory.timestamp.desc()).limit(limit).all()

            # Format for Claude (chronological order)
            context = []
            for h in reversed(history):
                context.append({
                    "role": h.role,
                    "content": h.content
                })

            return context

        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []
        finally:
            db.close()

    def get_returning_user_summary(self, phone: str) -> Optional[str]:
        """
        Generate a summary for returning users.
        Used to create personalized welcome back messages.
        """
        memory = self.get_user_memory(phone)

        if not memory.is_returning_user:
            return None

        parts = []

        # Name greeting
        if memory.name:
            if memory.days_since_last_chat > 7:
                parts.append(f"Welcome back, {memory.name}! It's been a while.")
            elif memory.days_since_last_chat > 0:
                parts.append(f"Hey {memory.name}, good to see you again!")
            else:
                parts.append(f"Back so soon, {memory.name}?")

        # What they were discussing
        if memory.politicians_asked_about:
            recent_politician = memory.politicians_asked_about[-1]
            parts.append(f"Last time you were asking about {recent_politician}.")

        if memory.topics_discussed:
            recent_topic = memory.topics_discussed[-1]
            parts.append(f"We were discussing {recent_topic}.")

        return " ".join(parts) if parts else None

    def _extract_topics(self, history: List[ChatHistory]) -> List[str]:
        """Extract topics from conversation history."""
        topics = []
        topic_keywords = {
            "election": "elections",
            "vote": "voting",
            "governor": "governors",
            "senator": "senate",
            "president": "presidency",
            "budget": "budgets",
            "education": "education",
            "security": "security",
            "economy": "economy",
            "2027": "2027 elections",
            "tinubu": "President Tinubu",
            "pvc": "voter registration",
        }

        for h in history:
            if h.role == "user" and h.content:
                content_lower = h.content.lower()
                for keyword, topic in topic_keywords.items():
                    if keyword in content_lower and topic not in topics:
                        topics.append(topic)

        return topics[-5:]  # Keep last 5 topics

    def _extract_politicians(self, history: List[ChatHistory]) -> List[str]:
        """Extract politician names from conversation history."""
        politicians = []
        # Common Nigerian politicians
        politician_names = [
            "tinubu", "atiku", "obi", "wike", "el-rufai",
            "osinbajo", "buhari", "jonathan", "saraki",
            "fashola", "sanwo-olu", "ganduje", "makinde"
        ]

        for h in history:
            if h.content:
                content_lower = h.content.lower()
                for name in politician_names:
                    if name in content_lower:
                        proper_name = name.title()
                        if proper_name not in politicians:
                            politicians.append(proper_name)

        return politicians[-5:]  # Keep last 5

    def update_user_profile(
        self,
        phone: str,
        name: Optional[str] = None,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Update user profile data."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user:
                # Create new user
                user = User(
                    phone_hash=user_hash,
                    created_at=datetime.utcnow()
                )
                db.add(user)

            if name:
                user.name = name
            if state:
                user.state = state
            if lga:
                user.lga = lga

            user.last_interaction = datetime.utcnow()

            # Update any additional fields
            for key, value in kwargs.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update user profile: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def get_user_stats(self, phone: str) -> Dict:
        """Get user engagement statistics."""
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Count messages
            total_messages = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).count()

            user_messages = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash,
                ChatHistory.role == "user"
            ).count()

            # Get first and last message dates
            first_msg = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).order_by(ChatHistory.timestamp.asc()).first()

            last_msg = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash
            ).order_by(ChatHistory.timestamp.desc()).first()

            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "first_interaction": first_msg.timestamp.isoformat() if first_msg else None,
                "last_interaction": last_msg.timestamp.isoformat() if last_msg else None,
            }

        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {}
        finally:
            db.close()


    def get_progressive_onboarding_prompt(self, phone: str) -> Optional[str]:
        """
        Get a progressive onboarding prompt based on user's interaction count.
        Returns None if no additional info is needed or it's not time to ask.
        """
        db = SessionLocal()
        try:
            user_hash = self._hash_phone(phone)

            # Get user and their preferences
            user = db.query(User).filter(User.phone_hash == user_hash).first()
            if not user:
                return None

            # Parse preferences
            import json
            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    prefs = {}

            # Count total messages
            total_messages = db.query(ChatHistory).filter(
                ChatHistory.phone_hash == user_hash,
                ChatHistory.role == "user"
            ).count()

            # Determine what to ask based on message count
            # Only ask at specific milestones (5, 15, 30 messages)
            last_asked = prefs.get("last_onboarding_ask_at", 0)

            # Progressive prompts at milestones
            prompts = []

            # After 5 messages - ask about voter registration
            if total_messages >= 5 and not prefs.get("has_pvc") and last_asked < 5:
                prompts.append({
                    "milestone": 5,
                    "question": "By the way, have you registered to vote? (Do you have your PVC?)",
                    "key": "pvc_asked"
                })

            # After 15 messages - ask about interests
            if total_messages >= 15 and not prefs.get("interests") and last_asked < 15:
                prompts.append({
                    "milestone": 15,
                    "question": "I notice you've been asking lots of good questions! What topics interest you most - economy, security, education, or healthcare?",
                    "key": "interests_asked"
                })

            # After 30 messages - ask about 2027 elections
            if total_messages >= 30 and not prefs.get("following_2027") and last_asked < 30:
                prompts.append({
                    "milestone": 30,
                    "question": "With 2027 elections approaching, are you planning to vote? Want me to help you track candidates in your area?",
                    "key": "election_asked"
                })

            # Select the appropriate prompt
            for prompt in prompts:
                if total_messages >= prompt["milestone"] and last_asked < prompt["milestone"]:
                    # Update last asked milestone
                    prefs["last_onboarding_ask_at"] = prompt["milestone"]
                    user.preferences_json = json.dumps(prefs)
                    db.commit()
                    return prompt["question"]

            return None

        except Exception as e:
            logger.error(f"Progressive onboarding error: {e}")
            return None
        finally:
            db.close()

    def save_progressive_response(self, phone: str, key: str, value: str) -> bool:
        """
        Save a progressive onboarding response.
        Keys: has_pvc, interests, following_2027
        """
        db = SessionLocal()
        try:
            import json
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user:
                return False

            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    prefs = {}

            prefs[key] = value
            user.preferences_json = json.dumps(prefs)
            db.commit()
            return True

        except Exception as e:
            logger.error(f"Save progressive response error: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def get_user_preferences(self, phone: str) -> Dict:
        """Get all user preferences as a dict."""
        db = SessionLocal()
        try:
            import json
            user_hash = self._hash_phone(phone)
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user or not user.preferences_json:
                return {}

            return json.loads(user.preferences_json)
        except Exception as e:
            logger.error(f"Get preferences error: {e}")
            return {}
        finally:
            db.close()


# Singleton instance
user_memory = UserMemoryService()
