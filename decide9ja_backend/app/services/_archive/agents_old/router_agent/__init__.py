"""
Router Agent

The entry point for all user messages.
Classifies intent and dispatches to specialist agents.
"""
from app.services.agents.router_agent.agent import RouterAgent

__all__ = ["RouterAgent"]
