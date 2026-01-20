"""NewsQueryAgent - Nigerian political news search and summarization"""
from app.agents.tier2_core.news_query.agent import NewsQueryAgent
from app.agents.tier2_core.news_query.prompt import SYSTEM_PROMPT

__all__ = ["NewsQueryAgent", "SYSTEM_PROMPT"]
