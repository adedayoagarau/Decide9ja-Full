"""
Election Agent

Handles all 2027 election-related queries:
- Candidate following/unfollowing
- Candidate comparisons
- Polling and voting
- Trending election topics
- Election information
"""
from app.services.agents.election_agent.agent import ElectionAgent

__all__ = ["ElectionAgent"]
