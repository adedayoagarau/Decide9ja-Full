"""
API Key Authentication for Decide9ja Admin APIs
"""
import os
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from functools import wraps

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# API Key header/query parameter names
API_KEY_HEADER = "X-API-Key"
API_KEY_QUERY = "api_key"

# Security schemes
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)
api_key_query = APIKeyQuery(name=API_KEY_QUERY, auto_error=False)


class APIKey(BaseModel):
    """API Key model."""
    key_id: str
    key_hash: str
    name: str
    role: str  # admin, moderator, viewer, api
    scopes: list[str]  # List of allowed operations
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    rate_limit: int = 1000  # requests per hour
    metadata: dict = {}


class APIKeyAuth:
    """API Key authentication handler."""

    # In-memory store (should be database in production)
    _keys: dict[str, APIKey] = {}
    _usage: dict[str, list[datetime]] = {}

    # Master admin key from environment
    MASTER_KEY = os.getenv("DECIDE9JA_ADMIN_KEY", "")

    @classmethod
    def initialize(cls):
        """Initialize with default keys from environment."""
        master_key = os.getenv("DECIDE9JA_ADMIN_KEY")
        if master_key:
            key_hash = cls._hash_key(master_key)
            cls._keys[key_hash] = APIKey(
                key_id="master",
                key_hash=key_hash,
                name="Master Admin Key",
                role="admin",
                scopes=["*"],
                created_by="system",
                created_at=datetime.utcnow(),
                is_active=True,
                rate_limit=10000
            )
            logger.info("Master admin key initialized")

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create_key(
        cls,
        name: str,
        role: str,
        scopes: list[str],
        created_by: str,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key.
        Returns the raw key (only shown once) and the key metadata.
        """
        # Generate secure random key
        raw_key = f"d9j_{secrets.token_urlsafe(32)}"
        key_hash = cls._hash_key(raw_key)
        key_id = secrets.token_hex(8)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            role=role,
            scopes=scopes,
            created_by=created_by,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True,
            rate_limit=rate_limit
        )

        cls._keys[key_hash] = api_key
        logger.info(f"Created API key: {key_id} for {name} with role {role}")

        return raw_key, api_key

    @classmethod
    def verify_key(cls, raw_key: str) -> Optional[APIKey]:
        """Verify an API key and return its metadata."""
        if not raw_key:
            return None

        key_hash = cls._hash_key(raw_key)
        api_key = cls._keys.get(key_hash)

        if not api_key:
            return None

        # Check if active
        if not api_key.is_active:
            logger.warning(f"Inactive API key used: {api_key.key_id}")
            return None

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {api_key.key_id}")
            return None

        # Check rate limit
        if not cls._check_rate_limit(key_hash, api_key.rate_limit):
            logger.warning(f"Rate limit exceeded for key: {api_key.key_id}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

        # Update last used
        api_key.last_used = datetime.utcnow()

        return api_key

    @classmethod
    def _check_rate_limit(cls, key_hash: str, limit: int) -> bool:
        """Check if key is within rate limit (requests per hour)."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Get recent requests
        requests = cls._usage.get(key_hash, [])

        # Filter to last hour
        recent = [r for r in requests if r > hour_ago]

        # Update usage
        recent.append(now)
        cls._usage[key_hash] = recent[-limit:]  # Keep only recent

        return len(recent) <= limit

    @classmethod
    def revoke_key(cls, key_id: str) -> bool:
        """Revoke an API key by ID."""
        for key_hash, api_key in cls._keys.items():
            if api_key.key_id == key_id:
                api_key.is_active = False
                logger.info(f"Revoked API key: {key_id}")
                return True
        return False

    @classmethod
    def list_keys(cls) -> list[dict]:
        """List all API keys (without hashes)."""
        return [
            {
                "key_id": k.key_id,
                "name": k.name,
                "role": k.role,
                "scopes": k.scopes,
                "created_at": k.created_at.isoformat(),
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used": k.last_used.isoformat() if k.last_used else None,
                "is_active": k.is_active,
            }
            for k in cls._keys.values()
        ]


# Initialize on import
APIKeyAuth.initialize()


async def get_api_key(
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> Optional[APIKey]:
    """
    FastAPI dependency to get and verify API key from header or query.
    """
    key = api_key_header or api_key_query

    if not key:
        return None

    return APIKeyAuth.verify_key(key)


async def require_api_key(
    api_key: Optional[APIKey] = Depends(get_api_key)
) -> APIKey:
    """
    FastAPI dependency that requires a valid API key.
    Raises 401 if no valid key provided.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return api_key


def verify_api_key(raw_key: str) -> Optional[APIKey]:
    """Verify an API key (sync wrapper)."""
    return APIKeyAuth.verify_key(raw_key)


def create_api_key(
    name: str,
    role: str,
    scopes: list[str],
    created_by: str,
    expires_in_days: Optional[int] = None
) -> Tuple[str, APIKey]:
    """Create a new API key (sync wrapper)."""
    return APIKeyAuth.create_key(name, role, scopes, created_by, expires_in_days)


def require_scope(scope: str):
    """
    Decorator to require a specific scope for an endpoint.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, api_key: APIKey = Depends(require_api_key), **kwargs):
            if "*" not in api_key.scopes and scope not in api_key.scopes:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required scope: {scope}"
                )
            return await func(*args, api_key=api_key, **kwargs)
        return wrapper
    return decorator
