"""
Performance & Caching Router
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.auth.api_keys import APIKey, require_api_key
from app.auth.rbac import Permission, check_permission
from app.services.cache import CacheService, CacheBackend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/performance", tags=["performance"])


# =====================
# Cache Management
# =====================

@router.get("/cache/stats")
async def get_cache_stats(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get cache statistics.
    Includes hit rate, memory usage, and key count.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    stats = await CacheService.get_stats()
    return stats.model_dump()


@router.get("/cache/health")
async def get_cache_health():
    """
    Check cache service health.
    No authentication required.
    """
    return await CacheService.health_check()


@router.post("/cache/clear")
async def clear_cache(
    namespace: Optional[str] = Query(None, description="Clear specific namespace only"),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Clear cache.
    Optionally clear only a specific namespace.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    success = await CacheService.clear(namespace)

    if success:
        return {
            "success": True,
            "message": f"Cache cleared{f' (namespace: {namespace})' if namespace else ''}"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to clear cache"
        )


@router.delete("/cache/key")
async def delete_cache_key(
    key: str = Query(..., description="Cache key to delete"),
    namespace: Optional[str] = Query(None),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Delete a specific cache key.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    success = await CacheService.delete(key, namespace)

    return {
        "success": success,
        "key": key,
        "namespace": namespace
    }


@router.delete("/cache/pattern")
async def delete_cache_pattern(
    pattern: str = Query(..., description="Pattern to match (e.g., 'user:*')"),
    namespace: Optional[str] = Query(None),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Delete cache keys matching a pattern.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    deleted = await CacheService.delete_pattern(pattern, namespace)

    return {
        "success": True,
        "pattern": pattern,
        "deleted_count": deleted
    }


# =====================
# Configuration
# =====================

@router.get("/cache/config")
async def get_cache_config(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get current cache configuration.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return {
        "backend": CacheService._backend.value,
        "redis_configured": CacheService._redis_url is not None,
        "default_ttls": CacheService.DEFAULT_TTLS,
        "key_prefix": CacheService.KEY_PREFIX
    }


# =====================
# Performance Metrics
# =====================

@router.get("/metrics")
async def get_performance_metrics(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get overall performance metrics.
    Includes response times, throughput, and error rates.
    """
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Analytics read permission required"
        )

    # Get cache stats
    cache_stats = await CacheService.get_stats()

    # These would come from actual monitoring in production
    metrics = {
        "cache": cache_stats.model_dump(),
        "api": {
            "requests_per_minute": 0,  # Would come from metrics collector
            "avg_response_time_ms": 0,
            "error_rate_percent": 0,
            "status_codes": {}
        },
        "database": {
            "connection_pool_size": 10,
            "active_connections": 0,
            "query_time_avg_ms": 0
        },
        "system": {
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0
        }
    }

    # Try to get system metrics
    try:
        import psutil
        metrics["system"]["cpu_percent"] = psutil.cpu_percent()
        metrics["system"]["memory_percent"] = psutil.virtual_memory().percent
        metrics["system"]["disk_percent"] = psutil.disk_usage('/').percent
    except ImportError:
        pass

    return metrics


@router.get("/slow-queries")
async def get_slow_queries(
    threshold_ms: int = Query(1000, description="Threshold in milliseconds"),
    limit: int = Query(20, ge=1, le=100),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get slow queries/requests.
    Useful for identifying performance bottlenecks.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    # In production, this would query a metrics store
    # For now, return structure
    return {
        "threshold_ms": threshold_ms,
        "limit": limit,
        "queries": []
    }


# =====================
# Rate Limiting Info
# =====================

@router.get("/rate-limits")
async def get_rate_limit_config(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get rate limiting configuration.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return {
        "enabled": True,
        "endpoints": {
            "/health": "60/minute",
            "/ask": "100/minute",
            "/search": "50/minute",
            "/webhook": "200/minute",
            "/location": "100/minute"
        },
        "default": "100/minute"
    }


# =====================
# Database Pool Info
# =====================

@router.get("/database/pool")
async def get_database_pool_info(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get database connection pool information.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    # This would come from SQLAlchemy engine in production
    return {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "checked_out": 0,
        "checked_in": 10,
        "overflow": 0
    }


# =====================
# Optimization Tips
# =====================

@router.get("/recommendations")
async def get_performance_recommendations(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get performance optimization recommendations.
    Based on current metrics and configuration.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    cache_stats = await CacheService.get_stats()
    recommendations = []

    # Cache recommendations
    if cache_stats.hit_rate < 50:
        recommendations.append({
            "category": "cache",
            "priority": "high",
            "message": f"Cache hit rate is low ({cache_stats.hit_rate}%). Consider increasing TTLs or caching more queries."
        })

    if CacheService._backend == CacheBackend.MEMORY:
        recommendations.append({
            "category": "cache",
            "priority": "medium",
            "message": "Using in-memory cache. Consider Redis for production for persistence and distributed caching."
        })

    # Database recommendations
    recommendations.append({
        "category": "database",
        "priority": "low",
        "message": "Consider adding indexes on frequently queried columns (user_hash, created_at, status)."
    })

    # API recommendations
    recommendations.append({
        "category": "api",
        "priority": "low",
        "message": "Enable response compression (gzip) for large responses."
    })

    return {
        "recommendations": recommendations,
        "metrics_summary": {
            "cache_hit_rate": cache_stats.hit_rate,
            "cache_backend": cache_stats.backend
        }
    }
