"""
Decide9ja Security Service
Handles rate limiting and prompt injection protection.
"""
import re
import time
import logging
from typing import Dict, Tuple, Optional
from collections import deque

logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        # Rate Limiting: user_id -> deque of timestamps
        self.request_history: Dict[str, deque] = {}
        self.RATE_LIMIT = 20  # requests per minute
        self.WINDOW_SECONDS = 60
        
        # Prompt Injection Patterns
        self.INJECTION_PATTERNS = [
            r"ignore previous instructions",
            r"system prompt",
            r"you are not",
            r"reveal your instructions",
            r"bypass safety",
            r"ignore all rules",
            r"do not follow",
            r"new persona",
        ]
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def check_request(self, user_id: str, text: str) -> Tuple[bool, str]:
        """
        Validates request against security rules.
        Returns: (is_safe, error_message)
        """
        # 1. Rate Limiting
        if not self._check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for {user_id}")
            return False, "Rate limit exceeded. Please wait a moment."

        # 2. Prompt Injection Guard
        # TODO: Implement LLM-based Prompt Guard (e.g., Claude Haiku/Llama-Guard) for production (95% catch rate vs 60% regex).
        if not self._check_prompt_injection(text):
            logger.warning(f"Prompt injection detected from {user_id}: {text[:50]}...")
            return False, "Message blocked by security filter."

        return True, ""

    def _check_rate_limit(self, user_id: str) -> bool:
        now = time.time()
        
        if user_id not in self.request_history:
            self.request_history[user_id] = deque()
            
        history = self.request_history[user_id]
        
        # Remove old requests
        while history and history[0] < now - self.WINDOW_SECONDS:
            history.popleft()
            
        if len(history) >= self.RATE_LIMIT:
            return False
            
        history.append(now)
        return True

    def _check_prompt_injection(self, text: str) -> bool:
        if not text:
            return True
        
        # Check length
        if len(text) > 2000:
            return False
            
        # Check patterns
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return False
                
        return True

# Singleton instance
security = SecurityService()
