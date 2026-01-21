"""
Civic Issues Agent - Handles community issue queries.

Intents:
- ISSUE_STATUS: Check status of reported issues
- ISSUE_TRENDING: Show trending issues
- LOCAL_ISSUES: Show issues in user's area
"""

from app.services.agents.civic_issues_agent.agent import CivicIssuesAgent

__all__ = ["CivicIssuesAgent"]
