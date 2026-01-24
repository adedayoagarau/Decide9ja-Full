"""
Civic Issues System - Database-backed community issue reporting.

Modular services:
- intake.py: Report new issues
- tracking.py: Track issue status
- aggregate.py: Community patterns and similar issues
"""

from app.services.civic_issues.intake import IssueIntakeService, issue_intake_service
from app.services.civic_issues.tracking import IssueTrackingService, issue_tracking_service
from app.services.civic_issues.aggregate import IssueAggregateService, issue_aggregate_service

__all__ = [
    "IssueIntakeService", "issue_intake_service",
    "IssueTrackingService", "issue_tracking_service",
    "IssueAggregateService", "issue_aggregate_service",
]
