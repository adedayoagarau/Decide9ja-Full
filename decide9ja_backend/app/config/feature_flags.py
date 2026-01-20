"""
Feature Flags Configuration
===========================
Central configuration for feature toggles.

Usage:
    from app.config.feature_flags import flags

    if flags.USE_V5:
        # Use new multi-agent system
    else:
        # Fall back to v4

Environment Variables:
    USE_V5: Enable multi-agent architecture (default: false)
    ENABLE_QUALITY_CHECKS: Enable response quality validation (default: true)
    ENABLE_ANALYTICS: Enable B2B analytics collection (default: true)
    ENABLE_CACHING: Enable response caching (default: true)
    DEBUG_AGENTS: Enable detailed agent logging (default: false)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer from environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_float_env(key: str, default: float) -> float:
    """Get float from environment variable"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class FeatureFlags:
    """
    Feature flags for controlling system behavior.

    All flags can be overridden via environment variables.
    """

    # ==========================================================================
    # CORE FLAGS
    # ==========================================================================

    # Multi-agent architecture toggle
    # Set to True to use v5 (multi-agent), False for v4 (monolithic)
    USE_V5: bool = field(default_factory=lambda: _get_bool_env("USE_V5", False))

    # Gradual rollout percentage (0-100)
    # When > 0, randomly routes that % of traffic to v5
    V5_ROLLOUT_PERCENTAGE: int = field(
        default_factory=lambda: _get_int_env("V5_ROLLOUT_PERCENTAGE", 0)
    )

    # ==========================================================================
    # QUALITY & SAFETY FLAGS
    # ==========================================================================

    # Enable response quality validation
    ENABLE_QUALITY_CHECKS: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_QUALITY_CHECKS", True)
    )

    # Enable prompt injection guards
    ENABLE_PROMPT_GUARDS: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_PROMPT_GUARDS", True)
    )

    # Auto-fallback to v4 on v5 errors
    AUTO_FALLBACK_ON_ERROR: bool = field(
        default_factory=lambda: _get_bool_env("AUTO_FALLBACK_ON_ERROR", True)
    )

    # Max consecutive errors before auto-disable v5
    MAX_CONSECUTIVE_ERRORS: int = field(
        default_factory=lambda: _get_int_env("MAX_CONSECUTIVE_ERRORS", 10)
    )

    # ==========================================================================
    # ANALYTICS FLAGS
    # ==========================================================================

    # Enable B2B analytics collection
    ENABLE_ANALYTICS: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_ANALYTICS", True)
    )

    # Enable detailed agent metrics
    ENABLE_AGENT_METRICS: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_AGENT_METRICS", True)
    )

    # ==========================================================================
    # PERFORMANCE FLAGS
    # ==========================================================================

    # Enable response caching
    ENABLE_CACHING: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_CACHING", True)
    )

    # Cache TTL in seconds (default: 1 hour)
    CACHE_TTL_SECONDS: int = field(
        default_factory=lambda: _get_int_env("CACHE_TTL_SECONDS", 3600)
    )

    # Enable simple query fast path (bypass agent chain for greetings/help)
    ENABLE_FAST_PATH: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_FAST_PATH", True)
    )

    # ==========================================================================
    # DEBUG FLAGS
    # ==========================================================================

    # Enable detailed agent logging
    DEBUG_AGENTS: bool = field(
        default_factory=lambda: _get_bool_env("DEBUG_AGENTS", False)
    )

    # Log all agent handoffs
    LOG_HANDOFFS: bool = field(
        default_factory=lambda: _get_bool_env("LOG_HANDOFFS", True)
    )

    # Log response times
    LOG_RESPONSE_TIMES: bool = field(
        default_factory=lambda: _get_bool_env("LOG_RESPONSE_TIMES", True)
    )

    # ==========================================================================
    # COST CONTROL FLAGS
    # ==========================================================================

    # Maximum LLM calls per request (safety limit)
    MAX_LLM_CALLS_PER_REQUEST: int = field(
        default_factory=lambda: _get_int_env("MAX_LLM_CALLS_PER_REQUEST", 3)
    )

    # Daily LLM budget in USD (0 = unlimited)
    DAILY_LLM_BUDGET_USD: float = field(
        default_factory=lambda: _get_float_env("DAILY_LLM_BUDGET_USD", 0.0)
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def should_use_v5(self, user_hash: Optional[str] = None) -> bool:
        """
        Determine if v5 should be used for this request.

        Supports gradual rollout based on user hash.
        """
        # Direct toggle takes precedence
        if self.USE_V5:
            return True

        # Check gradual rollout
        if self.V5_ROLLOUT_PERCENTAGE > 0 and user_hash:
            # Use hash to get consistent routing per user
            user_bucket = hash(user_hash) % 100
            return user_bucket < self.V5_ROLLOUT_PERCENTAGE

        return False

    def log_current_state(self):
        """Log current flag state"""
        logger.info(
            "Feature flags: USE_V5=%s, V5_ROLLOUT=%d%%, "
            "QUALITY_CHECKS=%s, ANALYTICS=%s, CACHING=%s",
            self.USE_V5,
            self.V5_ROLLOUT_PERCENTAGE,
            self.ENABLE_QUALITY_CHECKS,
            self.ENABLE_ANALYTICS,
            self.ENABLE_CACHING,
        )

    def to_dict(self) -> dict:
        """Export flags as dictionary"""
        return {
            "USE_V5": self.USE_V5,
            "V5_ROLLOUT_PERCENTAGE": self.V5_ROLLOUT_PERCENTAGE,
            "ENABLE_QUALITY_CHECKS": self.ENABLE_QUALITY_CHECKS,
            "ENABLE_PROMPT_GUARDS": self.ENABLE_PROMPT_GUARDS,
            "AUTO_FALLBACK_ON_ERROR": self.AUTO_FALLBACK_ON_ERROR,
            "ENABLE_ANALYTICS": self.ENABLE_ANALYTICS,
            "ENABLE_AGENT_METRICS": self.ENABLE_AGENT_METRICS,
            "ENABLE_CACHING": self.ENABLE_CACHING,
            "ENABLE_FAST_PATH": self.ENABLE_FAST_PATH,
            "DEBUG_AGENTS": self.DEBUG_AGENTS,
            "LOG_HANDOFFS": self.LOG_HANDOFFS,
            "LOG_RESPONSE_TIMES": self.LOG_RESPONSE_TIMES,
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global flags instance - import this in your code
flags = FeatureFlags()

# Log initial state on import
flags.log_current_state()


# =============================================================================
# RUNTIME CONTROL
# =============================================================================

_consecutive_errors = 0


def record_v5_error():
    """Record a v5 error for auto-disable logic"""
    global _consecutive_errors
    _consecutive_errors += 1

    if _consecutive_errors >= flags.MAX_CONSECUTIVE_ERRORS:
        logger.error(
            "V5 auto-disabled after %d consecutive errors",
            _consecutive_errors
        )
        flags.USE_V5 = False


def record_v5_success():
    """Record a v5 success, reset error counter"""
    global _consecutive_errors
    _consecutive_errors = 0


def get_error_count() -> int:
    """Get current consecutive error count"""
    return _consecutive_errors


def force_v5(enabled: bool):
    """Force v5 on/off (for testing/emergency)"""
    flags.USE_V5 = enabled
    logger.warning("V5 force-set to %s", enabled)


def set_rollout_percentage(percentage: int):
    """Set gradual rollout percentage (0-100)"""
    flags.V5_ROLLOUT_PERCENTAGE = max(0, min(100, percentage))
    logger.info("V5 rollout set to %d%%", flags.V5_ROLLOUT_PERCENTAGE)
