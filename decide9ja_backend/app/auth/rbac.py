"""
Role-Based Access Control (RBAC) for Decide9ja
"""
import logging
from enum import Enum
from typing import Optional, Set
from functools import wraps

from fastapi import HTTPException, Depends

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles with hierarchical permissions."""
    SUPER_ADMIN = "super_admin"  # Full access
    ADMIN = "admin"              # Manage all content, users, broadcasts
    MODERATOR = "moderator"      # Moderate content, fact-checks, issues
    EDITOR = "editor"            # Edit content, create fact-checks
    VIEWER = "viewer"            # Read-only access
    API = "api"                  # API access for integrations


class Permission(str, Enum):
    """Granular permissions for operations."""
    # Broadcast permissions
    BROADCAST_CREATE = "broadcast:create"
    BROADCAST_READ = "broadcast:read"
    BROADCAST_UPDATE = "broadcast:update"
    BROADCAST_DELETE = "broadcast:delete"
    BROADCAST_SEND = "broadcast:send"

    # Fact-check permissions
    FACTCHECK_CREATE = "factcheck:create"
    FACTCHECK_READ = "factcheck:read"
    FACTCHECK_UPDATE = "factcheck:update"
    FACTCHECK_DELETE = "factcheck:delete"
    FACTCHECK_VERIFY = "factcheck:verify"

    # Community issue permissions
    ISSUE_READ = "issue:read"
    ISSUE_UPDATE = "issue:update"
    ISSUE_DELETE = "issue:delete"
    ISSUE_MODERATE = "issue:moderate"

    # User management permissions
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_BAN = "user:ban"

    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    API_KEY_MANAGE = "apikey:manage"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # All permissions

    Role.ADMIN: {
        Permission.BROADCAST_CREATE,
        Permission.BROADCAST_READ,
        Permission.BROADCAST_UPDATE,
        Permission.BROADCAST_DELETE,
        Permission.BROADCAST_SEND,
        Permission.FACTCHECK_CREATE,
        Permission.FACTCHECK_READ,
        Permission.FACTCHECK_UPDATE,
        Permission.FACTCHECK_DELETE,
        Permission.FACTCHECK_VERIFY,
        Permission.ISSUE_READ,
        Permission.ISSUE_UPDATE,
        Permission.ISSUE_DELETE,
        Permission.ISSUE_MODERATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_BAN,
        Permission.ANALYTICS_READ,
        Permission.ANALYTICS_EXPORT,
        Permission.API_KEY_MANAGE,
    },

    Role.MODERATOR: {
        Permission.BROADCAST_READ,
        Permission.FACTCHECK_CREATE,
        Permission.FACTCHECK_READ,
        Permission.FACTCHECK_UPDATE,
        Permission.FACTCHECK_VERIFY,
        Permission.ISSUE_READ,
        Permission.ISSUE_UPDATE,
        Permission.ISSUE_MODERATE,
        Permission.USER_READ,
        Permission.ANALYTICS_READ,
    },

    Role.EDITOR: {
        Permission.BROADCAST_READ,
        Permission.FACTCHECK_CREATE,
        Permission.FACTCHECK_READ,
        Permission.FACTCHECK_UPDATE,
        Permission.ISSUE_READ,
        Permission.ANALYTICS_READ,
    },

    Role.VIEWER: {
        Permission.BROADCAST_READ,
        Permission.FACTCHECK_READ,
        Permission.ISSUE_READ,
        Permission.ANALYTICS_READ,
    },

    Role.API: {
        Permission.BROADCAST_READ,
        Permission.FACTCHECK_READ,
        Permission.ISSUE_READ,
        Permission.ANALYTICS_READ,
    },
}


def get_role_permissions(role: Role) -> Set[Permission]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


def check_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    try:
        role_enum = Role(role)
        permissions = get_role_permissions(role_enum)
        return permission in permissions
    except ValueError:
        logger.warning(f"Unknown role: {role}")
        return False


def require_role(*allowed_roles: Role):
    """
    Decorator factory to require specific roles.

    Usage:
        @require_role(Role.ADMIN, Role.MODERATOR)
        async def admin_endpoint(api_key: APIKey = Depends(require_api_key)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get api_key from kwargs (injected by require_api_key)
            api_key = kwargs.get('api_key')
            if not api_key:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )

            try:
                user_role = Role(api_key.role)
            except ValueError:
                raise HTTPException(
                    status_code=403,
                    detail=f"Invalid role: {api_key.role}"
                )

            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required role: {[r.value for r in allowed_roles]}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission: Permission):
    """
    Decorator factory to require a specific permission.

    Usage:
        @require_permission(Permission.BROADCAST_SEND)
        async def send_broadcast(api_key: APIKey = Depends(require_api_key)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            api_key = kwargs.get('api_key')
            if not api_key:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )

            if not check_permission(api_key.role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission.value}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RBACMiddleware:
    """
    Middleware class for role-based access control.
    Can be used for more complex authorization scenarios.
    """

    def __init__(self, default_role: Role = Role.VIEWER):
        self.default_role = default_role

    def can_access(self, role: str, permission: Permission) -> bool:
        """Check if role can access a permission."""
        return check_permission(role, permission)

    def get_allowed_actions(self, role: str) -> list[str]:
        """Get list of allowed actions for a role."""
        try:
            role_enum = Role(role)
            permissions = get_role_permissions(role_enum)
            return [p.value for p in permissions]
        except ValueError:
            return []

    def filter_by_role(self, items: list, role: str, permission_field: str = "required_permission") -> list:
        """
        Filter a list of items based on role permissions.
        Each item should have a field indicating required permission.
        """
        try:
            role_enum = Role(role)
            permissions = get_role_permissions(role_enum)

            return [
                item for item in items
                if not hasattr(item, permission_field) or
                getattr(item, permission_field) in permissions
            ]
        except ValueError:
            return []
