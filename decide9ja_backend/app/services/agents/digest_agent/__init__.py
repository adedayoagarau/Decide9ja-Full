"""
Digest Agent

Handles news digest subscriptions:
- Subscribe to daily/weekly digests
- Unsubscribe from digests
- Manage digest preferences
"""
from app.services.agents.digest_agent.agent import DigestAgent

__all__ = ["DigestAgent"]
