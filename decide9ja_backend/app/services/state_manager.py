"""
State management service.
Uses in-memory storage with optional Redis upgrade path.
Persists user profiles to PostgreSQL.
"""
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict
import os

from app.models.state import UserState, ConversationFlow

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
        self.session_ttl = 1800  # 30 minutes
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if URL is configured."""
        redis_url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Redis connected for session storage")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory storage: {e}")
                self.redis_client = None
    
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
        """Load user profile from PostgreSQL."""
        try:
            from app.database import get_db, User
            db = next(get_db())
            user = db.query(User).filter(User.phone_hash == user_id).first()
            if user:
                return {
                    "name": user.name,
                    "state": user.state,
                    "lga": user.lga
                }
        except Exception as e:
            logger.warning(f"Failed to load profile from DB: {e}")
        return None
    
    def _save_profile_to_db(self, state: UserState):
        """Save/update user profile in PostgreSQL."""
        try:
            from app.database import get_db, User
            db = next(get_db())
            
            user = db.query(User).filter(User.phone_hash == state.user_id).first()
            
            if user:
                user.name = state.name
                user.state = state.state
                user.lga = state.lga
                user.updated_at = datetime.utcnow()
            else:
                user = User(
                    phone_hash=state.user_id,
                    name=state.name,
                    state=state.state,
                    lga=state.lga
                )
                db.add(user)
            
            db.commit()
            logger.info(f"Saved profile for user {state.user_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to save profile to DB: {e}")


# Singleton instance
state_manager = StateManager()
