"""
Caching Service for Decide9ja
Redis-based caching with fallback to in-memory cache
"""
import os
import json
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any, Callable, TypeVar, Union
from functools import wraps
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheBackend(str, Enum):
    """Available cache backends."""
    REDIS = "redis"
    MEMORY = "memory"
    NONE = "none"


class CacheEntry(BaseModel):
    """A cached item with metadata."""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    hits: int = 0


class CacheStats(BaseModel):
    """Cache statistics."""
    backend: str
    total_keys: int
    hits: int
    misses: int
    hit_rate: float
    memory_usage_bytes: int


class CacheService:
    """
    Multi-backend caching service.
    Supports Redis (production) and in-memory (development).
    """

    # Configuration
    _backend: CacheBackend = CacheBackend.MEMORY
    _redis_client = None
    _redis_url: Optional[str] = None

    # In-memory cache
    _cache: dict = {}
    _stats = {
        "hits": 0,
        "misses": 0
    }

    # Default TTLs by category
    DEFAULT_TTLS = {
        "politician": 3600,       # 1 hour
        "election": 1800,         # 30 minutes
        "factcheck": 900,         # 15 minutes
        "news": 300,              # 5 minutes
        "user_session": 86400,    # 24 hours
        "query_result": 600,      # 10 minutes
        "dashboard": 300,         # 5 minutes
        "rate_limit": 3600,       # 1 hour
        "default": 600            # 10 minutes
    }

    # Key prefixes for namespacing
    KEY_PREFIX = "d9j:"

    @classmethod
    def initialize(cls, redis_url: Optional[str] = None):
        """Initialize the cache service."""
        url = redis_url or os.getenv("REDIS_URL")

        if url:
            try:
                import redis.asyncio as redis

                cls._redis_url = url
                cls._redis_client = redis.from_url(
                    url,
                    encoding="utf-8",
                    decode_responses=True
                )
                cls._backend = CacheBackend.REDIS
                logger.info(f"Redis cache initialized: {url[:30]}...")

            except ImportError:
                logger.warning("redis package not installed. Using in-memory cache.")
                cls._backend = CacheBackend.MEMORY
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                cls._backend = CacheBackend.MEMORY
        else:
            cls._backend = CacheBackend.MEMORY
            logger.info("Using in-memory cache (no Redis URL configured)")

    @classmethod
    def _make_key(cls, key: str, namespace: Optional[str] = None) -> str:
        """Generate a namespaced cache key."""
        if namespace:
            return f"{cls.KEY_PREFIX}{namespace}:{key}"
        return f"{cls.KEY_PREFIX}{key}"

    @classmethod
    def _serialize(cls, value: Any) -> str:
        """Serialize value for storage."""
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        elif isinstance(value, BaseModel):
            return value.model_dump_json()
        else:
            return json.dumps({"_value": value}, default=str)

    @classmethod
    def _deserialize(cls, data: str) -> Any:
        """Deserialize value from storage."""
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict) and "_value" in parsed:
                return parsed["_value"]
            return parsed
        except json.JSONDecodeError:
            return data

    @classmethod
    async def get(
        cls,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[Any]:
        """Get a value from cache."""
        full_key = cls._make_key(key, namespace)

        try:
            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                data = await cls._redis_client.get(full_key)
                if data:
                    cls._stats["hits"] += 1
                    return cls._deserialize(data)
                else:
                    cls._stats["misses"] += 1
                    return None

            else:
                # In-memory cache
                entry = cls._cache.get(full_key)
                if entry:
                    # Check expiration
                    if entry.expires_at and entry.expires_at < datetime.utcnow():
                        del cls._cache[full_key]
                        cls._stats["misses"] += 1
                        return None

                    entry.hits += 1
                    cls._stats["hits"] += 1
                    return entry.value
                else:
                    cls._stats["misses"] += 1
                    return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            cls._stats["misses"] += 1
            return None

    @classmethod
    async def set(
        cls,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """Set a value in cache."""
        full_key = cls._make_key(key, namespace)

        # Determine TTL
        if ttl is None:
            ttl = cls.DEFAULT_TTLS.get(namespace, cls.DEFAULT_TTLS["default"])

        try:
            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                serialized = cls._serialize(value)
                await cls._redis_client.setex(full_key, ttl, serialized)
                return True

            else:
                # In-memory cache
                expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
                cls._cache[full_key] = CacheEntry(
                    key=full_key,
                    value=value,
                    created_at=datetime.utcnow(),
                    expires_at=expires_at
                )

                # Cleanup old entries if cache is too large
                if len(cls._cache) > 10000:
                    cls._cleanup_memory_cache()

                return True

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    @classmethod
    async def delete(
        cls,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Delete a value from cache."""
        full_key = cls._make_key(key, namespace)

        try:
            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                await cls._redis_client.delete(full_key)
                return True
            else:
                if full_key in cls._cache:
                    del cls._cache[full_key]
                return True

        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    @classmethod
    async def delete_pattern(cls, pattern: str, namespace: Optional[str] = None) -> int:
        """Delete all keys matching a pattern."""
        full_pattern = cls._make_key(pattern, namespace)
        deleted = 0

        try:
            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                keys = await cls._redis_client.keys(full_pattern)
                if keys:
                    deleted = await cls._redis_client.delete(*keys)
            else:
                # In-memory: match keys
                import fnmatch
                to_delete = [k for k in cls._cache.keys() if fnmatch.fnmatch(k, full_pattern)]
                for k in to_delete:
                    del cls._cache[k]
                    deleted += 1

        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")

        return deleted

    @classmethod
    async def clear(cls, namespace: Optional[str] = None) -> bool:
        """Clear all cache or a specific namespace."""
        try:
            if namespace:
                pattern = f"{cls.KEY_PREFIX}{namespace}:*"
                await cls.delete_pattern(pattern)
            else:
                if cls._backend == CacheBackend.REDIS and cls._redis_client:
                    await cls._redis_client.flushdb()
                else:
                    cls._cache.clear()

            return True

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    @classmethod
    def _cleanup_memory_cache(cls):
        """Remove expired entries from in-memory cache."""
        now = datetime.utcnow()
        expired = [
            k for k, v in cls._cache.items()
            if v.expires_at and v.expires_at < now
        ]

        for k in expired:
            del cls._cache[k]

        # If still too large, remove oldest entries
        if len(cls._cache) > 8000:
            sorted_entries = sorted(
                cls._cache.items(),
                key=lambda x: x[1].created_at
            )
            for k, _ in sorted_entries[:2000]:
                del cls._cache[k]

        logger.info(f"Cache cleanup: removed {len(expired)} expired entries")

    @classmethod
    async def get_stats(cls) -> CacheStats:
        """Get cache statistics."""
        total_keys = 0
        memory_usage = 0

        try:
            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                info = await cls._redis_client.info("memory")
                total_keys = await cls._redis_client.dbsize()
                memory_usage = info.get("used_memory", 0)
            else:
                total_keys = len(cls._cache)
                # Estimate memory usage for in-memory cache
                memory_usage = sum(
                    len(cls._serialize(e.value))
                    for e in cls._cache.values()
                )
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")

        total_ops = cls._stats["hits"] + cls._stats["misses"]
        hit_rate = cls._stats["hits"] / total_ops * 100 if total_ops > 0 else 0

        return CacheStats(
            backend=cls._backend.value,
            total_keys=total_keys,
            hits=cls._stats["hits"],
            misses=cls._stats["misses"],
            hit_rate=round(hit_rate, 2),
            memory_usage_bytes=memory_usage
        )

    @classmethod
    async def health_check(cls) -> dict:
        """Check cache service health."""
        status = {
            "backend": cls._backend.value,
            "healthy": True,
            "latency_ms": None
        }

        try:
            import time
            start = time.time()

            if cls._backend == CacheBackend.REDIS and cls._redis_client:
                await cls._redis_client.ping()
            else:
                # Memory cache is always "healthy"
                pass

            status["latency_ms"] = round((time.time() - start) * 1000, 2)

        except Exception as e:
            status["healthy"] = False
            status["error"] = str(e)

        return status


def cached(
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl=300, namespace="politician")
        async def get_politician(name: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key from function name and args
                key_parts = [func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache
            cached_value = await CacheService.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await CacheService.set(cache_key, result, ttl, namespace)

            return result

        return wrapper
    return decorator


def cached_sync(
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator for caching synchronous function results.
    Uses asyncio.run for cache operations.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache (sync wrapper)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't use asyncio.run inside running loop
                    # Fall through to execute function
                    pass
                else:
                    cached_value = loop.run_until_complete(
                        CacheService.get(cache_key, namespace)
                    )
                    if cached_value is not None:
                        return cached_value
            except RuntimeError:
                pass

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.run_until_complete(
                        CacheService.set(cache_key, result, ttl, namespace)
                    )
            except RuntimeError:
                pass

            return result

        return wrapper
    return decorator


class QueryCache:
    """
    Specialized cache for database query results.
    Automatically invalidates on relevant writes.
    """

    @classmethod
    async def cache_query(
        cls,
        query_hash: str,
        result: Any,
        ttl: int = 600,
        tags: Optional[list] = None
    ):
        """Cache a query result with optional tags for invalidation."""
        await CacheService.set(query_hash, result, ttl, namespace="query")

        # Store tag mappings
        if tags:
            for tag in tags:
                tag_key = f"tag:{tag}"
                existing = await CacheService.get(tag_key, namespace="query_tags") or []
                if query_hash not in existing:
                    existing.append(query_hash)
                await CacheService.set(tag_key, existing, ttl * 2, namespace="query_tags")

    @classmethod
    async def invalidate_tag(cls, tag: str):
        """Invalidate all cached queries with a specific tag."""
        tag_key = f"tag:{tag}"
        query_hashes = await CacheService.get(tag_key, namespace="query_tags") or []

        for hash in query_hashes:
            await CacheService.delete(hash, namespace="query")

        await CacheService.delete(tag_key, namespace="query_tags")


# Initialize cache on import
CacheService.initialize()
