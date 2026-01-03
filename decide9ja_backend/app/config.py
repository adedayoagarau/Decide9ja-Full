"""
Decide9ja Backend - Centralized Configuration

Manages all environment variables and infrastructure settings.
Provides type-safe access with sensible defaults.
"""
import os
import logging
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


class Settings:
    """Application settings loaded from environment."""

    # ===========================================
    # ENVIRONMENT
    # ===========================================
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # ===========================================
    # DATABASE
    # ===========================================
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./decide9ja.db")

    # ===========================================
    # REDIS (Session Storage)
    # ===========================================
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
    REDIS_SESSION_TTL: int = int(os.getenv("REDIS_SESSION_TTL", "1800"))  # 30 minutes

    # ===========================================
    # SENTRY (Error Monitoring)
    # ===========================================
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    SENTRY_PROFILES_SAMPLE_RATE: float = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))

    # ===========================================
    # API KEYS
    # ===========================================
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # ===========================================
    # TWILIO (WhatsApp)
    # ===========================================
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER: Optional[str] = os.getenv("TWILIO_WHATSAPP_NUMBER")

    # ===========================================
    # SECURITY
    # ===========================================
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    # ===========================================
    # LOGGING
    # ===========================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" or "text"

    # ===========================================
    # VALIDATION
    # ===========================================
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def has_redis(self) -> bool:
        return bool(self.REDIS_URL)

    @property
    def has_sentry(self) -> bool:
        return bool(self.SENTRY_DSN)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    def validate(self) -> list:
        """
        Validate critical configuration.
        Returns list of warnings for missing optional services.
        """
        warnings = []

        # Critical (will fail without these)
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")

        # Important for production
        if self.is_production:
            if not self.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY required in production")

            if "*" in self.ALLOWED_ORIGINS:
                warnings.append("CORS allows all origins in production!")

        # Optional services
        if not self.has_redis:
            warnings.append("REDIS_URL not configured - using in-memory sessions (will lose state on restart)")

        if not self.has_sentry:
            warnings.append("SENTRY_DSN not configured - error monitoring disabled")

        return warnings


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure we only create one instance.
    """
    return Settings()


# Convenience function for logging setup
def setup_logging(settings: Settings = None):
    """
    Configure application logging.

    In production, uses JSON format for structured logging.
    In development, uses human-readable text format.
    """
    if settings is None:
        settings = get_settings()

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    if settings.LOG_FORMAT == "json" and settings.is_production:
        try:
            from pythonjsonlogger import jsonlogger

            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
                datefmt="%Y-%m-%dT%H:%M:%S%z"
            )
            console_handler.setFormatter(formatter)
        except ImportError:
            # Fallback to text format if pythonjsonlogger not available
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
    else:
        # Development: human-readable format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


def init_sentry(settings: Settings = None):
    """
    Initialize Sentry error monitoring.

    Only initializes if SENTRY_DSN is configured.
    """
    if settings is None:
        settings = get_settings()

    if not settings.has_sentry:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                ),
            ],
            # Don't send PII
            send_default_pii=False,
            # Filter sensitive data
            before_send=_filter_sensitive_data,
        )

        return True
    except ImportError:
        logging.warning("sentry-sdk not installed")
        return False
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {e}")
        return False


def _filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.

    Removes phone numbers, API keys, and other PII.
    """
    # Remove phone numbers from exception messages
    if "exception" in event:
        for exception in event.get("exception", {}).get("values", []):
            if exception.get("value"):
                # Mask phone numbers (Nigerian format)
                import re
                exception["value"] = re.sub(
                    r'\+?234\d{10}',
                    '[PHONE_REDACTED]',
                    str(exception["value"])
                )
                # Mask WhatsApp IDs
                exception["value"] = re.sub(
                    r'whatsapp:\+?\d+',
                    'whatsapp:[REDACTED]',
                    str(exception["value"])
                )

    # Remove sensitive request data
    if "request" in event:
        request = event["request"]

        # Remove authorization headers
        if "headers" in request:
            for header in ["authorization", "x-api-key"]:
                if header in request["headers"]:
                    request["headers"][header] = "[REDACTED]"

        # Remove body data that might contain secrets
        if "data" in request:
            if isinstance(request["data"], dict):
                for key in ["password", "token", "api_key", "secret"]:
                    if key in request["data"]:
                        request["data"][key] = "[REDACTED]"

    return event


# Export settings instance for easy import
settings = get_settings()
