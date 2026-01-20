"""
Fact Check Agent

Handles claim verification:
- Verify political claims
- Check facts against trusted sources
- Submit claims for review
"""
from app.services.agents.fact_check_agent.agent import FactCheckAgent

__all__ = ["FactCheckAgent"]
