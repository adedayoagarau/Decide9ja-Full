"""
Error Recovery Module for Decide9ja
====================================
Enhanced error handling with recovery strategies.

This module provides:
- Structured error classification
- Recovery strategies for different error types
- User-friendly error messages with options
- Graceful degradation paths

Usage:
    from enhancements.error_recovery import ErrorRecovery, ErrorType
    
    @ErrorRecovery.wrap
    async def my_handler(state, text):
        # Your code here
        pass
    
    # Or manually
    recovery = ErrorRecovery()
    result = await recovery.attempt(
        operation=fetch_data,
        error_context="fetching representatives",
        fallback=fallback_function
    )
"""

import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, List, Any, Callable, Coroutine, Union
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of error types for targeted recovery."""
    
    # User input errors
    INVALID_LOCATION = "invalid_location"
    AMBIGUOUS_QUERY = "ambiguous_query"
    MISSING_CONTEXT = "missing_context"
    RATE_LIMITED = "rate_limited"
    
    # System errors
    DATABASE_ERROR = "database_error"
    API_FAILURE = "api_failure"
    TIMEOUT = "timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # Data errors
    NO_RESULTS = "no_results"
    DATA_INCOMPLETE = "data_incomplete"
    DATA_STALE = "data_stale"
    
    # LLM errors
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_CONTEXT_OVERFLOW = "llm_context_overflow"
    LLM_HALLUCINATION_DETECTED = "llm_hallucination_detected"
    
    # Tool errors
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_INVALID_PARAMS = "tool_invalid_params"
    
    # Unknown
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Available recovery strategies."""
    
    RETRY = "retry"                           # Simple retry
    RETRY_WITH_BACKOFF = "retry_with_backoff" # Exponential backoff
    FALLBACK = "fallback"                     # Use fallback method
    CLARIFY = "clarify"                       # Ask user for clarification
    SIMPLIFY = "simplify"                     # Simplify the request
    DEGRADE = "degrade"                       # Graceful degradation
    ESCALATE = "escalate"                     # Pass to human/handoff
    RESET = "reset"                           # Reset state and start over


@dataclass
class ErrorRecord:
    """Record of an error for tracking and analysis."""
    error_type: ErrorType
    message: str
    context: str
    timestamp: Any  # datetime
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    recovery_attempted: Optional[str] = None
    recovery_successful: bool = False
    

@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    response: Optional[str] = None
    new_state: Optional[str] = None
    action_required: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# User-friendly error templates
ERROR_TEMPLATES = {
    ErrorType.INVALID_LOCATION: {
        "message": "I couldn't understand that location. ",
        "options": [
            "Try using your state name (e.g., 'Lagos', 'Kano')",
            "Add your LGA if you know it (e.g., 'Ikeja, Lagos')",
            "Say 'skip' if you prefer not to share"
        ]
    },
    ErrorType.AMBIGUOUS_QUERY: {
        "message": "I'm not sure what you're asking about. ",
        "options": [
            "Try asking about a specific politician",
            "Ask about your representatives using your location",
            "Say 'menu' to see what I can help with"
        ]
    },
    ErrorType.DATABASE_ERROR: {
        "message": "I'm having trouble accessing my records right now. ",
        "options": [
            "Please try again in a moment",
            "Ask something else while I sort this out"
        ]
    },
    ErrorType.API_FAILURE: {
        "message": "I'm having trouble connecting to external services. ",
        "options": [
            "Try again in a few minutes",
            "I can answer general questions without external data"
        ]
    },
    ErrorType.TIMEOUT: {
        "message": "That took longer than expected. ",
        "options": [
            "Try a simpler question",
            "Try again - the service might be busy"
        ]
    },
    ErrorType.NO_RESULTS: {
        "message": "I couldn't find any information about that. ",
        "options": [
            "Try different keywords",
            "Check the spelling of names",
            "Ask about something else"
        ]
    },
    ErrorType.LLM_TIMEOUT: {
        "message": "I'm thinking too slowly about that one. ",
        "options": [
            "Let me give you a simpler answer",
            "Try rephrasing your question"
        ]
    },
    ErrorType.LLM_RATE_LIMIT: {
        "message": "I'm a bit overwhelmed right now. ",
        "options": [
            "Please try again in a minute",
            "I can still help with basic questions"
        ]
    },
    ErrorType.TOOL_EXECUTION_FAILED: {
        "message": "I couldn't complete that action. ",
        "options": [
            "Let me try a different approach",
            "Please try again"
        ]
    },
    ErrorType.UNKNOWN: {
        "message": "Something unexpected happened. ",
        "options": [
            "Try again or ask something else",
            "Say 'reset' to start fresh"
        ]
    }
}


class ErrorRecovery:
    """
    Enhanced error recovery system for Decide9ja.
    
    Provides classification, recovery strategies, and user-friendly
    error messages with actionable options.
    """
    
    def __init__(self):
        self.error_history: List[ErrorRecord] = []
        self.max_history = 100
        self.retry_delays = [1, 2, 4]  # Exponential backoff delays
        
    def classify_error(self, exception: Exception, context: str = "") -> ErrorType:
        """
        Classify an exception into an ErrorType.
        
        Args:
            exception: The caught exception
            context: Additional context about where the error occurred
            
        Returns:
            The classified ErrorType
        """
        error_msg = str(exception).lower()
        exc_type = type(exception).__name__
        
        # Location errors
        if any(kw in error_msg for kw in ["location", "state", "lga", "not found"]):
            if "ambiguous" in error_msg or "multiple" in error_msg:
                return ErrorType.AMBIGUOUS_QUERY
            return ErrorType.INVALID_LOCATION
        
        # Database errors
        if any(kw in exc_type.lower() for kw in ["sql", "database", "db", "sqlite"]):
            return ErrorType.DATABASE_ERROR
        
        # Timeout errors
        if any(kw in error_msg for kw in ["timeout", "timed out", "time out"]):
            if "llm" in context.lower() or "claude" in context.lower():
                return ErrorType.LLM_TIMEOUT
            return ErrorType.TIMEOUT
        
        # Rate limiting
        if any(kw in error_msg for kw in ["rate limit", "too many", "throttle"]):
            if "llm" in context.lower() or "claude" in context.lower():
                return ErrorType.LLM_RATE_LIMIT
            return ErrorType.RATE_LIMITED
        
        # API errors
        if any(kw in exc_type.lower() for kw in ["api", "http", "connection", "network"]):
            return ErrorType.API_FAILURE
        
        # No results
        if any(kw in error_msg for kw in ["no results", "not found", "empty", "none found"]):
            return ErrorType.NO_RESULTS
        
        # Tool errors
        if "tool" in context.lower():
            if "not found" in error_msg:
                return ErrorType.TOOL_NOT_FOUND
            if "param" in error_msg or "argument" in error_msg:
                return ErrorType.TOOL_INVALID_PARAMS
            return ErrorType.TOOL_EXECUTION_FAILED
        
        # LLM errors
        if "llm" in context.lower() or "claude" in context.lower():
            if "context" in error_msg or "token" in error_msg:
                return ErrorType.LLM_CONTEXT_OVERFLOW
            if "hallucination" in error_msg:
                return ErrorType.LLM_HALLUCINATION_DETECTED
        
        return ErrorType.UNKNOWN
    
    def get_user_message(self, error_type: ErrorType, custom_message: Optional[str] = None) -> str:
        """
        Generate a user-friendly error message with options.
        
        Args:
            error_type: The type of error
            custom_message: Optional custom message to prepend
            
        Returns:
            Formatted error message with options
        """
        template = ERROR_TEMPLATES.get(error_type, ERROR_TEMPLATES[ErrorType.UNKNOWN])
        
        message = custom_message or template["message"]
        options = template.get("options", [])
        
        if options:
            message += "\n\nYou can:\n"
            for i, option in enumerate(options, 1):
                message += f"{i}. {option}\n"
        
        return message.strip()
    
    def get_recovery_strategy(self, error_type: ErrorType) -> List[RecoveryStrategy]:
        """
        Get recommended recovery strategies for an error type.
        
        Returns a list of strategies in priority order.
        """
        strategy_map = {
            ErrorType.INVALID_LOCATION: [RecoveryStrategy.CLARIFY, RecoveryStrategy.FALLBACK],
            ErrorType.AMBIGUOUS_QUERY: [RecoveryStrategy.CLARIFY, RecoveryStrategy.SIMPLIFY],
            ErrorType.DATABASE_ERROR: [RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.FALLBACK],
            ErrorType.API_FAILURE: [RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.DEGRADE],
            ErrorType.TIMEOUT: [RecoveryStrategy.RETRY, RecoveryStrategy.SIMPLIFY],
            ErrorType.NO_RESULTS: [RecoveryStrategy.CLARIFY, RecoveryStrategy.SIMPLIFY],
            ErrorType.LLM_TIMEOUT: [RecoveryStrategy.RETRY, RecoveryStrategy.SIMPLIFY, RecoveryStrategy.DEGRADE],
            ErrorType.LLM_RATE_LIMIT: [RecoveryStrategy.RETRY_WITH_BACKOFF, RecoveryStrategy.DEGRADE],
            ErrorType.LLM_CONTEXT_OVERFLOW: [RecoveryStrategy.SIMPLIFY, RecoveryStrategy.DEGRADE],
            ErrorType.TOOL_EXECUTION_FAILED: [RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK],
        }
        
        return strategy_map.get(error_type, [RecoveryStrategy.RETRY, RecoveryStrategy.RESET])
    
    async def attempt(
        self,
        operation: Callable[[], Coroutine],
        error_context: str = "",
        fallback: Optional[Callable[[], Coroutine]] = None,
        max_retries: int = 2,
        user_id: Optional[str] = None
    ) -> RecoveryResult:
        """
        Attempt an operation with automatic recovery.
        
        Args:
            operation: The async operation to attempt
            error_context: Context string for error classification
            fallback: Optional fallback operation
            max_retries: Maximum retry attempts
            user_id: User ID for error tracking
            
        Returns:
            RecoveryResult with success status and response
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await operation()
                return RecoveryResult(
                    success=True,
                    response=result if isinstance(result, str) else None,
                    metadata={"attempts": attempt + 1}
                )
            except Exception as e:
                last_exception = e
                error_type = self.classify_error(e, error_context)
                
                # Log the error
                self._log_error(error_type, str(e), error_context, e, user_id)
                
                # Determine if we should retry
                strategies = self.get_recovery_strategy(error_type)
                
                if RecoveryStrategy.RETRY_WITH_BACKOFF in strategies and attempt < max_retries:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.info(f"Retrying after {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                elif RecoveryStrategy.RETRY in strategies and attempt < max_retries:
                    logger.info(f"Retrying immediately (attempt {attempt + 1})")
                    continue
                else:
                    # Don't retry, try fallback or fail
                    break
        
        # Try fallback if available
        if fallback:
            try:
                fallback_result = await fallback()
                return RecoveryResult(
                    success=True,
                    response=fallback_result if isinstance(fallback_result, str) else None,
                    metadata={"fallback_used": True}
                )
            except Exception as e:
                logger.error(f"Fallback also failed: {e}")
        
        # Generate error message
        error_type = self.classify_error(last_exception, error_context)
        user_message = self.get_user_message(error_type)
        
        return RecoveryResult(
            success=False,
            response=user_message,
            action_required="user_input",
            metadata={
                "error_type": error_type.value,
                "original_error": str(last_exception)
            }
        )
    
    def _log_error(
        self,
        error_type: ErrorType,
        message: str,
        context: str,
        exception: Exception,
        user_id: Optional[str] = None
    ) -> None:
        """Log an error for tracking."""
        record = ErrorRecord(
            error_type=error_type,
            message=message,
            context=context,
            timestamp=__import__('datetime').datetime.utcnow(),
            stack_trace=traceback.format_exc(),
            user_id=user_id
        )
        
        self.error_history.append(record)
        
        # Keep only recent errors
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]
        
        # Log to system
        logger.error(f"[{error_type.value}] {context}: {message}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        if not self.error_history:
            return {"total": 0}
        
        from collections import Counter
        type_counts = Counter(e.error_type.value for e in self.error_history)
        
        return {
            "total": len(self.error_history),
            "by_type": dict(type_counts),
            "recent": [
                {
                    "type": e.error_type.value,
                    "context": e.context,
                    "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp)
                }
                for e in self.error_history[-5:]
            ]
        }
    
    @staticmethod
    def wrap(
        error_context: str = "",
        fallback_message: Optional[str] = None,
        log_errors: bool = True
    ):
        """
        Decorator for wrapping async functions with error recovery.
        
        Usage:
            @ErrorRecovery.wrap(error_context="fetching data")
            async def my_function(state, text):
                return await fetch_something()
        """
        def decorator(func: Callable):
            recovery = ErrorRecovery()
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_type = recovery.classify_error(e, error_context)
                    
                    if log_errors:
                        recovery._log_error(error_type, str(e), error_context, e)
                    
                    # Get user-friendly message
                    message = recovery.get_user_message(error_type)
                    if fallback_message:
                        message = f"{fallback_message}\n\n{message}"
                    
                    return message
            
            return wrapper
        return decorator


# Convenience functions for common error scenarios

def handle_location_error(location_input: str) -> str:
    """
    Generate a helpful message for location errors.
    
    Args:
        location_input: The location string that caused the error
        
    Returns:
        User-friendly error message with suggestions
    """
    suggestions = []
    
    # Check for common misspellings
    if len(location_input) < 3:
        suggestions.append("Location names need at least 3 characters")
    
    if any(char.isdigit() for char in location_input):
        suggestions.append("I don't need numbers - just the state/LGA name")
    
    return f"""I couldn't understand "{location_input}" as a location.

{suggestions[0] if suggestions else "Try entering your state name (e.g., 'Lagos', 'Kano', 'Rivers')"}

I can understand:
• State names (37 in Nigeria)
• LGA names (774 across all states)
• Common nicknames (e.g., 'Abuja' for FCT)

Which state are you in?"""


def handle_empty_results(query_type: str, query: str) -> str:
    """Generate message when no results are found."""
    return f"""I couldn't find any {query_type} matching "{query}".

This might mean:
• The information isn't in my database yet
• There might be a spelling difference
• The query might need to be more specific

Try:
• Checking the spelling
• Using a different name or term
• Asking about something else

What else can I help you find?"""


def handle_service_unavailable(service_name: str) -> str:
    """Generate message when a service is unavailable."""
    return f"""I'm having trouble accessing {service_name} right now.

This is usually temporary. You can:
• Try again in a few minutes
• Ask me something that doesn't need {service_name}

I can still help with:
• Questions about politicians in my database
• General Nigerian politics information
• Your saved preferences and history

What would you like to know?"""


# Singleton instance
_recovery_instance: Optional[ErrorRecovery] = None


def get_error_recovery() -> ErrorRecovery:
    """Get the global error recovery instance."""
    global _recovery_instance
    if _recovery_instance is None:
        _recovery_instance = ErrorRecovery()
    return _recovery_instance