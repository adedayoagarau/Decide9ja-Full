"""
Audit Logging for Decide9ja Admin Operations
"""
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from functools import wraps

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"

    # Broadcast operations
    BROADCAST_CREATED = "broadcast_created"
    BROADCAST_UPDATED = "broadcast_updated"
    BROADCAST_SCHEDULED = "broadcast_scheduled"
    BROADCAST_SENT = "broadcast_sent"
    BROADCAST_PAUSED = "broadcast_paused"
    BROADCAST_CANCELLED = "broadcast_cancelled"

    # Fact-check operations
    FACTCHECK_CREATED = "factcheck_created"
    FACTCHECK_UPDATED = "factcheck_updated"
    FACTCHECK_DELETED = "factcheck_deleted"
    FACTCHECK_REQUEST_PROCESSED = "factcheck_request_processed"

    # Community issue operations
    ISSUE_STATUS_UPDATED = "issue_status_updated"
    ISSUE_DELETED = "issue_deleted"
    ISSUE_MODERATED = "issue_moderated"

    # User operations
    USER_UPDATED = "user_updated"
    USER_BANNED = "user_banned"
    USER_UNBANNED = "user_unbanned"

    # System operations
    CONFIG_UPDATED = "config_updated"
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"


class AuditEntry(BaseModel):
    """Audit log entry."""
    timestamp: datetime
    action: AuditAction
    actor_id: str  # API key ID or user ID
    actor_role: str
    resource_type: str  # broadcast, factcheck, issue, user, etc.
    resource_id: Optional[str] = None
    details: dict = {}
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class AuditLogger:
    """
    Audit logging service.
    Stores audit logs for compliance and security review.
    """

    # In-memory storage (should be database in production)
    _logs: list[AuditEntry] = []
    _max_logs = 10000

    @classmethod
    def log(
        cls,
        action: AuditAction,
        actor_id: str,
        actor_role: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: dict = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditEntry:
        """Log an audit entry."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )

        cls._logs.append(entry)

        # Trim old logs
        if len(cls._logs) > cls._max_logs:
            cls._logs = cls._logs[-cls._max_logs:]

        # Also log to standard logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT: {action.value} by {actor_id} ({actor_role}) on {resource_type}/{resource_id or 'N/A'}"
        )

        return entry

    @classmethod
    def get_logs(
        cls,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """Query audit logs with filters."""
        filtered = cls._logs.copy()

        if action:
            filtered = [e for e in filtered if e.action == action]
        if actor_id:
            filtered = [e for e in filtered if e.actor_id == actor_id]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if resource_id:
            filtered = [e for e in filtered if e.resource_id == resource_id]
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        # Sort by timestamp descending
        filtered.sort(key=lambda x: x.timestamp, reverse=True)

        # Paginate
        paginated = filtered[offset:offset + limit]

        return [e.model_dump() for e in paginated]

    @classmethod
    def get_stats(cls, days: int = 7) -> dict:
        """Get audit log statistics."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        recent = [e for e in cls._logs if e.timestamp >= cutoff]

        action_counts = {}
        for entry in recent:
            action_counts[entry.action.value] = action_counts.get(entry.action.value, 0) + 1

        actor_counts = {}
        for entry in recent:
            actor_counts[entry.actor_id] = actor_counts.get(entry.actor_id, 0) + 1

        success_count = sum(1 for e in recent if e.success)
        failure_count = sum(1 for e in recent if not e.success)

        return {
            "period_days": days,
            "total_entries": len(recent),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_count / len(recent) * 100, 1) if recent else 0,
            "by_action": action_counts,
            "by_actor": dict(sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
        }

    @classmethod
    def export_logs(
        cls,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json"
    ) -> str:
        """Export audit logs to JSON or CSV."""
        logs = cls.get_logs(
            start_time=start_time,
            end_time=end_time,
            limit=cls._max_logs
        )

        if format == "json":
            return json.dumps(logs, default=str, indent=2)
        elif format == "csv":
            if not logs:
                return ""

            headers = list(logs[0].keys())
            lines = [",".join(headers)]

            for log in logs:
                values = []
                for h in headers:
                    val = log.get(h, "")
                    if isinstance(val, dict):
                        val = json.dumps(val)
                    values.append(f'"{val}"')
                lines.append(",".join(values))

            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")


def audit_log(
    action: AuditAction,
    resource_type: str,
    get_resource_id: callable = None,
    get_details: callable = None
):
    """
    Decorator to automatically log audit entries for endpoint functions.

    Usage:
        @audit_log(AuditAction.BROADCAST_CREATED, "broadcast", lambda r: r.get("campaign_id"))
        async def create_broadcast(data: BroadcastCreate, api_key: APIKey = Depends(require_api_key)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            api_key = kwargs.get('api_key')
            request = kwargs.get('request')

            actor_id = api_key.key_id if api_key else "anonymous"
            actor_role = api_key.role if api_key else "unknown"
            ip_address = request.client.host if request else None
            user_agent = request.headers.get("user-agent") if request else None

            try:
                result = await func(*args, **kwargs)

                # Extract resource ID and details from result
                resource_id = None
                details = {}

                if get_resource_id and isinstance(result, dict):
                    resource_id = get_resource_id(result)

                if get_details and isinstance(result, dict):
                    details = get_details(result)

                AuditLogger.log(
                    action=action,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True
                )

                return result

            except Exception as e:
                AuditLogger.log(
                    action=action,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    resource_type=resource_type,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message=str(e)
                )
                raise

        return wrapper
    return decorator
