"""
State management service.
Uses in-memory storage with optional Redis upgrade path.
Persists user profiles to PostgreSQL.
"""
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict

from app.models.state import UserState, ConversationFlow
from app.config import settings

logger = logging.getLogger(__name__)

# In-memory session store (replaced by Redis in production)
_session_store: Dict[str, str] = {}


class StateManager:
    """
    Manages user state across conversations.

    Storage strategy:
    - Session data (flow, context, history): In-memory dict (or Redis if configured)
    - Profile data (name, state, lga): PostgreSQL for persistence
    """

    def __init__(self):
        self.session_ttl = settings.REDIS_SESSION_TTL
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if URL is configured."""
        if settings.has_redis:
            try:
                import redis
                self.redis_client = redis.from_url(settings.REDIS_URL)
                self.redis_client.ping()
                logger.info(f"Redis connected for session storage (TTL: {self.session_ttl}s)")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory storage: {e}")
                self.redis_client = None
        else:
            logger.info("Redis not configured, using in-memory session storage")
    
    def _hash_phone(self, phone: str) -> str:
        """Create consistent hash of phone number."""
        # Clean phone number
        clean_phone = phone.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        return hashlib.sha256(clean_phone.encode()).hexdigest()[:16]
    
    def get_state(self, phone: str) -> UserState:
        """
        Load user state synchronously.
        Checks cache first, falls back to PostgreSQL, creates new if needed.
        """
        user_id = self._hash_phone(phone)
        redis_key = f"session:{user_id}"
        
        # Try cache first (Redis or in-memory)
        cached = self._get_cached(redis_key)
        if cached:
            try:
                state = UserState.from_redis(cached, phone)
                
                # Check for expired flow
                if state.is_flow_expired():
                    state.clear_flow()
                
                # Check for expired context
                if state.is_context_expired():
                    state.clear_context()
                
                return state
            except Exception as e:
                logger.warning(f"Failed to deserialize state: {e}")
        
        # Try PostgreSQL (user exists but session expired)
        profile = self._load_profile_from_db(user_id)
        
        if profile:
            state = UserState(
                user_id=user_id,
                phone=phone,
                name=profile.get("name"),
                state=profile.get("state"),
                lga=profile.get("lga"),
                greeted=False,  # New session, will greet again
                session_start=datetime.utcnow()
            )
        else:
            # New user - start onboarding
            state = UserState(
                user_id=user_id,
                phone=phone,
                flow=ConversationFlow.ONBOARDING,
                flow_step=0,
                session_start=datetime.utcnow()
            )
        
        # Cache the state
        self.save_state(state)
        return state
    
    def save_state(self, state: UserState):
        """Save state to cache (and PostgreSQL for profile data)."""
        state.last_message_at = datetime.utcnow()
        redis_key = f"session:{state.user_id}"
        
        # Save to cache
        self._set_cached(redis_key, state.to_redis(), self.session_ttl)
        
        # Save profile to PostgreSQL if onboarding complete
        if state.is_onboarding_complete():
            self._save_profile_to_db(state)
    
    def clear_session(self, phone: str):
        """Clear session (for 'reset' command)."""
        user_id = self._hash_phone(phone)
        redis_key = f"session:{user_id}"
        self._delete_cached(redis_key)
    
    def delete_user_data(self, phone: str) -> bool:
        """
        Delete ALL user data (for 'delete my data' / 'forget me' commands).
        This is a GDPR-style full deletion from all systems.
        
        Args:
            phone: User's phone number
            
        Returns:
            True if deletion was successful
        """
        user_id = self._hash_phone(phone)
        redis_key = f"session:{user_id}"
        
        success = True
        
        # 1. Delete from Redis/cache
        try:
            self._delete_cached(redis_key)
            logger.info(f"Deleted session for user {user_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            success = False
        
        # 2. Delete from PostgreSQL
        try:
            from app.database import get_db, User, ChatHistory, UserReport
            db = next(get_db())
            
            # Delete user profile
            user = db.query(User).filter(User.phone_hash == user_id).first()
            if user:
                db.delete(user)
            
            # Delete chat history
            db.query(ChatHistory).filter(ChatHistory.phone_hash == user_id).delete()
            
            # Delete user reports (or anonymize)
            db.query(UserReport).filter(UserReport.user_hash == user_id).update(
                {"user_hash": "deleted"},
                synchronize_session=False
            )
            
            db.commit()
            logger.info(f"Deleted PostgreSQL data for user {user_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to delete PostgreSQL data: {e}")
            success = False
        
        return success
    
    # ==========================================
    # Cache Operations (Redis or In-Memory)
    # ==========================================
    
    def _get_cached(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                return value.decode() if value else None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        return _session_store.get(key)
    
    def _set_cached(self, key: str, value: str, ttl: int):
        """Set value in cache with TTL."""
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        _session_store[key] = value
    
    def _delete_cached(self, key: str):
        """Delete value from cache."""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
                return
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        _session_store.pop(key, None)
    
    # ==========================================
    # Database Operations
    # ==========================================
    
    def _load_profile_from_db(self, user_id: str) -> Optional[dict]:
        """Load user profile from PostgreSQL using raw SQL."""
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT name, state, lga FROM users 
                    WHERE phone_hash = :user_id
                    LIMIT 1
                '''), {'user_id': user_id})
                row = result.fetchone()
                
                if row:
                    return {
                        "name": row[0],
                        "state": row[1],
                        "lga": row[2]
                    }
        except Exception as e:
            logger.warning(f"Failed to load profile from DB: {e}")
        return None
    
    def _save_profile_to_db(self, state: UserState):
        """Save/update user profile in PostgreSQL using raw SQL."""
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                # Check if user exists
                result = conn.execute(text('''
                    SELECT id FROM users WHERE phone_hash = :user_id
                '''), {'user_id': state.user_id})
                existing = result.fetchone()
                
                if existing:
                    # Update existing user
                    conn.execute(text('''
                        UPDATE users SET 
                            name = :name, 
                            state = :state, 
                            lga = :lga,
                            onboarding_completed = TRUE,
                            updated_at = NOW(),
                            last_interaction = NOW()
                        WHERE phone_hash = :user_id
                    '''), {
                        'user_id': state.user_id,
                        'name': state.name,
                        'state': state.state,
                        'lga': state.lga
                    })
                else:
                    # Insert new user
                    conn.execute(text('''
                        INSERT INTO users (phone_hash, name, state, lga, onboarding_completed)
                        VALUES (:user_id, :name, :state, :lga, TRUE)
                    '''), {
                        'user_id': state.user_id,
                        'name': state.name,
                        'state': state.state,
                        'lga': state.lga
                    })
                
                conn.commit()
                logger.info(f"Saved profile for user {state.user_id[:8]}... (name={state.name})")
        except Exception as e:
            logger.error(f"Failed to save profile to DB: {e}")


# Singleton instance
state_manager = StateManager()


# Async wrapper functions (used by message handlers)
async def _get_state_async(phone: str) -> UserState:
    """Async wrapper to get user state."""
    return state_manager.get_state(phone)


async def _save_state_async(state: UserState):
    """Async wrapper to save user state."""
    state_manager.save_state(state)

