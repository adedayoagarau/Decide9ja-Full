"""
Authentication & API Key Management Router
"""
import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field

from app.auth.api_keys import (
    APIKeyAuth,
    APIKey,
    require_api_key,
    get_api_key
)
from app.auth.rbac import Role, Permission, check_permission
from app.auth.audit import AuditLogger, AuditAction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


# =====================
# Pydantic Models
# =====================

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    role: str = Field(default="viewer")  # admin, moderator, editor, viewer, api
    scopes: List[str] = []
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    rate_limit: int = Field(default=1000, ge=10, le=100000)


class APIKeyResponse(BaseModel):
    """API key metadata response."""
    key_id: str
    name: str
    role: str
    scopes: List[str]
    created_at: str
    expires_at: Optional[str]
    last_used: Optional[str]
    is_active: bool


class CreateAPIKeyResponse(BaseModel):
    """Response when creating API key (includes raw key)."""
    success: bool
    api_key: str  # Only shown once!
    key_id: str
    name: str
    role: str
    message: str


# =====================
# API Key Endpoints
# =====================

@router.post("/keys", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: Request,
    data: CreateAPIKeyRequest,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Create a new API key.
    Requires admin role.
    """
    # Check permission
    if not check_permission(api_key.role, Permission.API_KEY_MANAGE):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to manage API keys"
        )

    # Validate role
    try:
        Role(data.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {data.role}. Valid roles: {[r.value for r in Role]}"
        )

    # Can't create keys with higher privileges
    role_hierarchy = {
        Role.SUPER_ADMIN: 5,
        Role.ADMIN: 4,
        Role.MODERATOR: 3,
        Role.EDITOR: 2,
        Role.VIEWER: 1,
        Role.API: 1
    }

    creator_level = role_hierarchy.get(Role(api_key.role), 0)
    target_level = role_hierarchy.get(Role(data.role), 0)

    if target_level > creator_level:
        raise HTTPException(
            status_code=403,
            detail="Cannot create API key with higher privileges than your own"
        )

    # Create the key
    raw_key, new_key = APIKeyAuth.create_key(
        name=data.name,
        role=data.role,
        scopes=data.scopes,
        created_by=api_key.key_id,
        expires_in_days=data.expires_in_days,
        rate_limit=data.rate_limit
    )

    # Audit log
    AuditLogger.log(
        action=AuditAction.API_KEY_CREATED,
        actor_id=api_key.key_id,
        actor_role=api_key.role,
        resource_type="api_key",
        resource_id=new_key.key_id,
        details={
            "name": data.name,
            "role": data.role,
            "scopes": data.scopes
        },
        ip_address=request.client.host if request.client else None
    )

    return CreateAPIKeyResponse(
        success=True,
        api_key=raw_key,
        key_id=new_key.key_id,
        name=new_key.name,
        role=new_key.role,
        message="API key created. Store the key securely - it won't be shown again!"
    )


@router.get("/keys")
async def list_api_keys(
    api_key: APIKey = Depends(require_api_key)
):
    """
    List all API keys.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.API_KEY_MANAGE):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view API keys"
        )

    keys = APIKeyAuth.list_keys()

    return {
        "total": len(keys),
        "keys": keys
    }


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Revoke an API key.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.API_KEY_MANAGE):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to revoke API keys"
        )

    # Can't revoke own key
    if key_id == api_key.key_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot revoke your own API key"
        )

    success = APIKeyAuth.revoke_key(key_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )

    # Audit log
    AuditLogger.log(
        action=AuditAction.API_KEY_REVOKED,
        actor_id=api_key.key_id,
        actor_role=api_key.role,
        resource_type="api_key",
        resource_id=key_id,
        ip_address=request.client.host if request.client else None
    )

    return {
        "success": True,
        "message": f"API key {key_id} revoked"
    }


@router.get("/me")
async def get_current_key(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get information about the current API key.
    """
    return {
        "key_id": api_key.key_id,
        "name": api_key.name,
        "role": api_key.role,
        "scopes": api_key.scopes,
        "created_at": api_key.created_at.isoformat(),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
        "rate_limit": api_key.rate_limit
    }


@router.get("/verify")
async def verify_key(
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """
    Verify if an API key is valid.
    Returns key info if valid, error if not.
    """
    if not api_key:
        return {
            "valid": False,
            "message": "Invalid or missing API key"
        }

    return {
        "valid": True,
        "key_id": api_key.key_id,
        "role": api_key.role,
        "scopes": api_key.scopes
    }


# =====================
# Audit Log Endpoints
# =====================

@router.get("/audit")
async def get_audit_logs(
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Query audit logs.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view audit logs"
        )

    # Parse action enum
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}"
            )

    # Parse dates
    start_time = None
    end_time = None
    if start_date:
        start_time = datetime.fromisoformat(start_date)
    if end_date:
        end_time = datetime.fromisoformat(end_date)

    logs = AuditLogger.get_logs(
        action=action_enum,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )

    return {
        "total": len(logs),
        "offset": offset,
        "limit": limit,
        "logs": logs
    }


@router.get("/audit/stats")
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get audit log statistics.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view audit stats"
        )

    return AuditLogger.get_stats(days=days)


@router.get("/audit/export")
async def export_audit_logs(
    format: str = Query("json", regex="^(json|csv)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Export audit logs.
    Requires admin role with export permission.
    """
    if not check_permission(api_key.role, Permission.ANALYTICS_EXPORT):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to export audit logs"
        )

    start_time = None
    end_time = None
    if start_date:
        start_time = datetime.fromisoformat(start_date)
    if end_date:
        end_time = datetime.fromisoformat(end_date)

    # Log the export action
    AuditLogger.log(
        action=AuditAction.DATA_EXPORTED,
        actor_id=api_key.key_id,
        actor_role=api_key.role,
        resource_type="audit_logs",
        details={"format": format, "start_date": start_date, "end_date": end_date}
    )

    data = AuditLogger.export_logs(
        start_time=start_time,
        end_time=end_time,
        format=format
    )

    return {
        "format": format,
        "data": data
    }


# =====================
# Role & Permission Info
# =====================

@router.get("/roles")
async def list_roles():
    """
    List available roles and their permissions.
    Public endpoint for documentation.
    """
    from app.auth.rbac import ROLE_PERMISSIONS

    roles_info = {}
    for role in Role:
        permissions = ROLE_PERMISSIONS.get(role, set())
        roles_info[role.value] = {
            "name": role.value,
            "permissions": [p.value for p in permissions]
        }

    return {
        "roles": roles_info
    }


@router.get("/permissions")
async def list_permissions():
    """
    List available permissions.
    Public endpoint for documentation.
    """
    return {
        "permissions": [p.value for p in Permission]
    }
