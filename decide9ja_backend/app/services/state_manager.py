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
                # Enhanced location profile
                origin_state=profile.get("origin_state"),
                origin_lga=profile.get("origin_lga"),
                residence_state=profile.get("residence_state"),
                residence_lga=profile.get("residence_lga"),
                registered_state=profile.get("registered_state"),
                registered_lga=profile.get("registered_lga"),
                ward=profile.get("ward"),
                # Political geography
                senatorial_district=profile.get("senatorial_district"),
                federal_constituency=profile.get("federal_constituency"),
                state_constituency=profile.get("state_constituency"),
                # Demographics
                age_range=profile.get("age_range"),
                gender=profile.get("gender"),
                has_pvc=profile.get("has_pvc"),
                # Interests
                interests=profile.get("interests", []),
                topics_asked=profile.get("topics_asked", []),
                profile_completeness=profile.get("profile_completeness", 0),
                # Session
                greeted=False,  # New session, will greet again
                session_start=datetime.utcnow(),
                last_active_at=profile.get("last_active_at"),  # When they last used the bot
                message_count=profile.get("message_count", 0)
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

        # Auto-derive political geography if user has location
        if state.is_onboarding_complete():
            self.derive_political_geography(state)

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
    # Political Geography Derivation
    # ==========================================

    def derive_political_geography(self, state: UserState) -> bool:
        """
        Auto-derive political geography (senatorial district, federal constituency)
        from the user's state and LGA using the lga_representatives table.

        Returns True if geography was updated, False otherwise.
        """
        if not state.state or not state.lga:
            return False

        # Skip if already derived
        if state.senatorial_district and state.federal_constituency:
            return False

        try:
            from sqlalchemy import create_engine, text
            import os

            engine = create_engine(os.getenv('DATABASE_URL'))
            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT senatorial_district, federal_constituency
                    FROM lga_representatives
                    WHERE state = :state AND lga = :lga
                    LIMIT 1
                '''), {'state': state.state, 'lga': state.lga})
                row = result.fetchone()

                if row:
                    state.senatorial_district = row[0]
                    state.federal_constituency = row[1]
                    logger.info(f"Derived geography for {state.state}/{state.lga}: {row[0]}, {row[1]}")
                    return True

                # Try fuzzy match
                result = conn.execute(text('''
                    SELECT senatorial_district, federal_constituency
                    FROM lga_representatives
                    WHERE state = :state AND (lga ILIKE :lga_pattern OR :lga ILIKE '%' || lga || '%')
                    LIMIT 1
                '''), {'state': state.state, 'lga': state.lga, 'lga_pattern': f"%{state.lga}%"})
                row = result.fetchone()

                if row:
                    state.senatorial_district = row[0]
                    state.federal_constituency = row[1]
                    logger.info(f"Derived geography (fuzzy) for {state.state}/{state.lga}: {row[0]}, {row[1]}")
                    return True

        except Exception as e:
            logger.warning(f"Failed to derive political geography: {e}")

        return False

    # ==========================================
    # Database Operations
    # ==========================================

    def _load_profile_from_db(self, user_id: str) -> Optional[dict]:
        """Load user profile from PostgreSQL using raw SQL."""
        try:
            from sqlalchemy import create_engine, text
            import os

            engine = create_engine(os.getenv('DATABASE_URL'))
            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT name, state, lga, last_interaction, message_count,
                           origin_state, origin_lga, residence_state, residence_lga,
                           registered_state, registered_lga, ward,
                           senatorial_district, federal_constituency, state_constituency,
                           age_range, gender, has_pvc, interests, topics_asked,
                           profile_completeness
                    FROM users
                    WHERE phone_hash = :user_id
                    LIMIT 1
                '''), {'user_id': user_id})
                row = result.fetchone()

                if row:
                    return {
                        "name": row[0],
                        "state": row[1],
                        "lga": row[2],
                        "last_active_at": row[3],  # datetime or None
                        "message_count": row[4] or 0,
                        # Enhanced location profile
                        "origin_state": row[5],
                        "origin_lga": row[6],
                        "residence_state": row[7],
                        "residence_lga": row[8],
                        "registered_state": row[9],
                        "registered_lga": row[10],
                        "ward": row[11],
                        # Political geography
                        "senatorial_district": row[12],
                        "federal_constituency": row[13],
                        "state_constituency": row[14],
                        # Demographics
                        "age_range": row[15],
                        "gender": row[16],
                        "has_pvc": row[17],
                        # Interests (stored as TEXT[] in PostgreSQL)
                        "interests": list(row[18]) if row[18] else [],
                        "topics_asked": list(row[19]) if row[19] else [],
                        "profile_completeness": row[20] or 0,
                    }
        except Exception as e:
            logger.warning(f"Failed to load profile from DB: {e}")
        return None
    
    def _save_profile_to_db(self, state: UserState):
        """Save/update user profile in PostgreSQL using raw SQL."""
        try:
            from sqlalchemy import create_engine, text
            import os

            # Update profile completeness before saving
            state.update_profile_completeness()

            engine = create_engine(os.getenv('DATABASE_URL'))
            with engine.connect() as conn:
                # Check if user exists
                result = conn.execute(text('''
                    SELECT id FROM users WHERE phone_hash = :user_id
                '''), {'user_id': state.user_id})
                existing = result.fetchone()

                if existing:
                    # Update existing user with all fields
                    conn.execute(text('''
                        UPDATE users SET
                            name = :name,
                            state = :state,
                            lga = :lga,
                            origin_state = COALESCE(:origin_state, origin_state),
                            origin_lga = COALESCE(:origin_lga, origin_lga),
                            residence_state = COALESCE(:residence_state, residence_state),
                            residence_lga = COALESCE(:residence_lga, residence_lga),
                            registered_state = COALESCE(:registered_state, registered_state),
                            registered_lga = COALESCE(:registered_lga, registered_lga),
                            ward = COALESCE(:ward, ward),
                            senatorial_district = COALESCE(:senatorial_district, senatorial_district),
                            federal_constituency = COALESCE(:federal_constituency, federal_constituency),
                            state_constituency = COALESCE(:state_constituency, state_constituency),
                            age_range = COALESCE(:age_range, age_range),
                            gender = COALESCE(:gender, gender),
                            has_pvc = COALESCE(:has_pvc, has_pvc),
                            interests = :interests,
                            topics_asked = :topics_asked,
                            profile_completeness = :profile_completeness,
                            onboarding_completed = TRUE,
                            updated_at = NOW(),
                            last_interaction = NOW(),
                            message_count = COALESCE(message_count, 0) + 1
                        WHERE phone_hash = :user_id
                    '''), {
                        'user_id': state.user_id,
                        'name': state.name,
                        'state': state.state,
                        'lga': state.lga,
                        'origin_state': state.origin_state,
                        'origin_lga': state.origin_lga,
                        'residence_state': state.residence_state,
                        'residence_lga': state.residence_lga,
                        'registered_state': state.registered_state,
                        'registered_lga': state.registered_lga,
                        'ward': state.ward,
                        'senatorial_district': state.senatorial_district,
                        'federal_constituency': state.federal_constituency,
                        'state_constituency': state.state_constituency,
                        'age_range': state.age_range,
                        'gender': state.gender,
                        'has_pvc': state.has_pvc,
                        'interests': state.interests if state.interests else None,
                        'topics_asked': state.topics_asked if state.topics_asked else None,
                        'profile_completeness': state.profile_completeness,
                    })
                else:
                    # Insert new user with all fields
                    conn.execute(text('''
                        INSERT INTO users (
                            phone_hash, name, state, lga,
                            origin_state, origin_lga, residence_state, residence_lga,
                            registered_state, registered_lga, ward,
                            senatorial_district, federal_constituency, state_constituency,
                            age_range, gender, has_pvc,
                            interests, topics_asked, profile_completeness,
                            onboarding_completed, message_count, last_interaction
                        )
                        VALUES (
                            :user_id, :name, :state, :lga,
                            :origin_state, :origin_lga, :residence_state, :residence_lga,
                            :registered_state, :registered_lga, :ward,
                            :senatorial_district, :federal_constituency, :state_constituency,
                            :age_range, :gender, :has_pvc,
                            :interests, :topics_asked, :profile_completeness,
                            TRUE, 1, NOW()
                        )
                    '''), {
                        'user_id': state.user_id,
                        'name': state.name,
                        'state': state.state,
                        'lga': state.lga,
                        'origin_state': state.origin_state,
                        'origin_lga': state.origin_lga,
                        'residence_state': state.residence_state,
                        'residence_lga': state.residence_lga,
                        'registered_state': state.registered_state,
                        'registered_lga': state.registered_lga,
                        'ward': state.ward,
                        'senatorial_district': state.senatorial_district,
                        'federal_constituency': state.federal_constituency,
                        'state_constituency': state.state_constituency,
                        'age_range': state.age_range,
                        'gender': state.gender,
                        'has_pvc': state.has_pvc,
                        'interests': state.interests if state.interests else None,
                        'topics_asked': state.topics_asked if state.topics_asked else None,
                        'profile_completeness': state.profile_completeness,
                    })

                conn.commit()
                logger.info(f"Saved profile for user {state.user_id[:8]}... (name={state.name}, completeness={state.profile_completeness}%)")
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

