"""
Tests for Authentication System - API Keys, RBAC, Audit Logging
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Import auth modules
from app.auth.api_keys import APIKeyAuth, APIKey, verify_api_key
from app.auth.rbac import (
    Role, Permission, check_permission,
    get_role_permissions, ROLE_PERMISSIONS
)
from app.auth.audit import AuditLogger, AuditAction, AuditEntry


class TestAPIKeys:
    """Tests for API key management."""

    def setup_method(self):
        """Reset state before each test."""
        APIKeyAuth._keys = {}
        APIKeyAuth._usage = {}

    def test_create_key_returns_raw_and_metadata(self):
        """Test that creating a key returns both raw key and metadata."""
        raw_key, api_key = APIKeyAuth.create_key(
            name="Test Key",
            role="viewer",
            scopes=["read"],
            created_by="test_creator"
        )

        assert raw_key.startswith("d9j_")
        assert len(raw_key) > 40
        assert api_key.name == "Test Key"
        assert api_key.role == "viewer"
        assert api_key.is_active is True

    def test_verify_valid_key(self):
        """Test verifying a valid API key."""
        raw_key, _ = APIKeyAuth.create_key(
            name="Valid Key",
            role="admin",
            scopes=["*"],
            created_by="system"
        )

        verified = APIKeyAuth.verify_key(raw_key)
        assert verified is not None
        assert verified.name == "Valid Key"
        assert verified.role == "admin"

    def test_verify_invalid_key_returns_none(self):
        """Test that invalid keys return None."""
        result = APIKeyAuth.verify_key("invalid_key_12345")
        assert result is None

    def test_verify_empty_key_returns_none(self):
        """Test that empty keys return None."""
        assert APIKeyAuth.verify_key("") is None
        assert APIKeyAuth.verify_key(None) is None

    def test_revoke_key(self):
        """Test revoking an API key."""
        raw_key, api_key = APIKeyAuth.create_key(
            name="Revoke Test",
            role="viewer",
            scopes=[],
            created_by="test"
        )

        # Verify key works
        assert APIKeyAuth.verify_key(raw_key) is not None

        # Revoke it
        success = APIKeyAuth.revoke_key(api_key.key_id)
        assert success is True

        # Should no longer work
        assert APIKeyAuth.verify_key(raw_key) is None

    def test_revoke_nonexistent_key_returns_false(self):
        """Test that revoking nonexistent key returns False."""
        result = APIKeyAuth.revoke_key("nonexistent_id")
        assert result is False

    def test_key_expiration(self):
        """Test that expired keys are rejected."""
        # Create key with very short expiration (we can't actually set it to be already expired)
        raw_key, api_key = APIKeyAuth.create_key(
            name="Expiring Key",
            role="viewer",
            scopes=[],
            created_by="test",
            expires_in_days=1
        )

        # Manually set expiration to past
        api_key.expires_at = datetime.utcnow() - timedelta(hours=1)

        # Should be rejected
        result = APIKeyAuth.verify_key(raw_key)
        assert result is None

    def test_list_keys(self):
        """Test listing all keys."""
        APIKeyAuth.create_key("Key1", "viewer", [], "test")
        APIKeyAuth.create_key("Key2", "admin", ["*"], "test")

        keys = APIKeyAuth.list_keys()
        assert len(keys) == 2
        names = [k["name"] for k in keys]
        assert "Key1" in names
        assert "Key2" in names

    def test_key_with_custom_rate_limit(self):
        """Test creating key with custom rate limit."""
        raw_key, api_key = APIKeyAuth.create_key(
            name="High Rate Key",
            role="api",
            scopes=["read"],
            created_by="test",
            rate_limit=5000
        )

        assert api_key.rate_limit == 5000

    def test_key_updates_last_used(self):
        """Test that verifying key updates last_used timestamp."""
        raw_key, api_key = APIKeyAuth.create_key(
            name="Usage Tracking",
            role="viewer",
            scopes=[],
            created_by="test"
        )

        assert api_key.last_used is None

        APIKeyAuth.verify_key(raw_key)
        assert api_key.last_used is not None


class TestRBAC:
    """Tests for Role-Based Access Control."""

    def test_all_roles_exist(self):
        """Test that all expected roles are defined."""
        assert Role.SUPER_ADMIN.value == "super_admin"
        assert Role.ADMIN.value == "admin"
        assert Role.MODERATOR.value == "moderator"
        assert Role.EDITOR.value == "editor"
        assert Role.VIEWER.value == "viewer"
        assert Role.API.value == "api"

    def test_super_admin_has_all_permissions(self):
        """Test that super_admin has all permissions."""
        permissions = get_role_permissions(Role.SUPER_ADMIN)
        # Should have all permissions
        for perm in Permission:
            assert perm in permissions

    def test_viewer_has_read_only_permissions(self):
        """Test that viewer only has read permissions."""
        permissions = get_role_permissions(Role.VIEWER)

        # Should have read permissions
        assert Permission.BROADCAST_READ in permissions
        assert Permission.FACTCHECK_READ in permissions
        assert Permission.ISSUE_READ in permissions
        assert Permission.ANALYTICS_READ in permissions

        # Should NOT have write permissions
        assert Permission.BROADCAST_CREATE not in permissions
        assert Permission.FACTCHECK_DELETE not in permissions
        assert Permission.USER_BAN not in permissions

    def test_check_permission_valid(self):
        """Test checking valid permission."""
        assert check_permission("admin", Permission.BROADCAST_CREATE) is True
        assert check_permission("viewer", Permission.BROADCAST_READ) is True

    def test_check_permission_invalid(self):
        """Test checking invalid permission."""
        assert check_permission("viewer", Permission.BROADCAST_CREATE) is False
        assert check_permission("editor", Permission.USER_BAN) is False

    def test_check_permission_invalid_role(self):
        """Test that invalid role returns False."""
        assert check_permission("invalid_role", Permission.BROADCAST_READ) is False

    def test_moderator_can_moderate(self):
        """Test that moderator has moderation permissions."""
        assert check_permission("moderator", Permission.ISSUE_MODERATE) is True
        assert check_permission("moderator", Permission.FACTCHECK_VERIFY) is True
        assert check_permission("moderator", Permission.FACTCHECK_UPDATE) is True

    def test_admin_can_manage_api_keys(self):
        """Test that admin can manage API keys."""
        assert check_permission("admin", Permission.API_KEY_MANAGE) is True
        assert check_permission("moderator", Permission.API_KEY_MANAGE) is False

    def test_permission_hierarchy(self):
        """Test that roles have appropriate permission hierarchy."""
        # Admin should have more than moderator
        admin_perms = get_role_permissions(Role.ADMIN)
        mod_perms = get_role_permissions(Role.MODERATOR)

        assert len(admin_perms) > len(mod_perms)

        # Moderator should have more than viewer
        viewer_perms = get_role_permissions(Role.VIEWER)
        assert len(mod_perms) > len(viewer_perms)


class TestAuditLogging:
    """Tests for Audit Logging."""

    def setup_method(self):
        """Reset audit logs before each test."""
        AuditLogger._logs = []

    def test_log_creates_entry(self):
        """Test that logging creates an audit entry."""
        entry = AuditLogger.log(
            action=AuditAction.API_KEY_CREATED,
            actor_id="test_actor",
            actor_role="admin",
            resource_type="api_key",
            resource_id="key_123"
        )

        assert entry.action == AuditAction.API_KEY_CREATED
        assert entry.actor_id == "test_actor"
        assert entry.resource_id == "key_123"
        assert entry.success is True

    def test_log_with_failure(self):
        """Test logging a failed action."""
        entry = AuditLogger.log(
            action=AuditAction.BROADCAST_CREATED,
            actor_id="test_actor",
            actor_role="admin",
            resource_type="broadcast",
            success=False,
            error_message="Permission denied"
        )

        assert entry.success is False
        assert entry.error_message == "Permission denied"

    def test_log_with_details(self):
        """Test logging with additional details."""
        entry = AuditLogger.log(
            action=AuditAction.CONFIG_UPDATED,
            actor_id="admin1",
            actor_role="super_admin",
            resource_type="config",
            details={"key": "api_rate_limit", "old_value": 100, "new_value": 200}
        )

        assert entry.details["key"] == "api_rate_limit"
        assert entry.details["new_value"] == 200

    def test_get_logs_returns_recent_first(self):
        """Test that logs are returned most recent first."""
        AuditLogger.log(
            action=AuditAction.LOGIN,
            actor_id="user1",
            actor_role="viewer",
            resource_type="session"
        )
        AuditLogger.log(
            action=AuditAction.LOGOUT,
            actor_id="user2",
            actor_role="viewer",
            resource_type="session"
        )

        logs = AuditLogger.get_logs()
        assert len(logs) == 2
        # Most recent (LOGOUT) should be first
        assert logs[0]["action"] == "logout"

    def test_get_logs_filter_by_action(self):
        """Test filtering logs by action."""
        AuditLogger.log(AuditAction.LOGIN, "u1", "viewer", "session")
        AuditLogger.log(AuditAction.LOGOUT, "u2", "viewer", "session")
        AuditLogger.log(AuditAction.LOGIN, "u3", "viewer", "session")

        logs = AuditLogger.get_logs(action=AuditAction.LOGIN)
        assert len(logs) == 2
        assert all(log["action"] == "login" for log in logs)

    def test_get_logs_filter_by_actor(self):
        """Test filtering logs by actor."""
        AuditLogger.log(AuditAction.LOGIN, "user_a", "viewer", "session")
        AuditLogger.log(AuditAction.LOGIN, "user_b", "viewer", "session")
        AuditLogger.log(AuditAction.LOGOUT, "user_a", "viewer", "session")

        logs = AuditLogger.get_logs(actor_id="user_a")
        assert len(logs) == 2
        assert all(log["actor_id"] == "user_a" for log in logs)

    def test_get_logs_pagination(self):
        """Test log pagination."""
        for i in range(10):
            AuditLogger.log(
                AuditAction.LOGIN,
                f"user_{i}",
                "viewer",
                "session"
            )

        page1 = AuditLogger.get_logs(limit=3, offset=0)
        page2 = AuditLogger.get_logs(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0] != page2[0]

    def test_get_stats(self):
        """Test audit statistics."""
        AuditLogger.log(AuditAction.LOGIN, "u1", "viewer", "session")
        AuditLogger.log(AuditAction.LOGIN, "u2", "viewer", "session")
        AuditLogger.log(
            AuditAction.API_KEY_CREATED, "admin", "admin", "api_key",
            success=False
        )

        stats = AuditLogger.get_stats(days=7)

        assert stats["total_entries"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["by_action"]["login"] == 2

    def test_export_json(self):
        """Test exporting logs as JSON."""
        AuditLogger.log(AuditAction.LOGIN, "u1", "viewer", "session")

        export = AuditLogger.export_logs(format="json")
        assert "login" in export
        assert "u1" in export

    def test_export_csv(self):
        """Test exporting logs as CSV."""
        AuditLogger.log(AuditAction.LOGIN, "u1", "viewer", "session")

        export = AuditLogger.export_logs(format="csv")
        assert "timestamp" in export
        assert "action" in export
        assert "login" in export

    def test_max_logs_limit(self):
        """Test that logs are trimmed when exceeding max."""
        original_max = AuditLogger._max_logs
        AuditLogger._max_logs = 5

        for i in range(10):
            AuditLogger.log(AuditAction.LOGIN, f"u{i}", "viewer", "session")

        assert len(AuditLogger._logs) == 5

        # Restore
        AuditLogger._max_logs = original_max


class TestAuditActions:
    """Tests for audit action types."""

    def test_all_action_types_exist(self):
        """Test that all expected action types are defined."""
        # Authentication
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.API_KEY_CREATED.value == "api_key_created"

        # Broadcast
        assert AuditAction.BROADCAST_CREATED.value == "broadcast_created"
        assert AuditAction.BROADCAST_SENT.value == "broadcast_sent"

        # Fact-check
        assert AuditAction.FACTCHECK_CREATED.value == "factcheck_created"

        # Community issues
        assert AuditAction.ISSUE_STATUS_UPDATED.value == "issue_status_updated"

        # System
        assert AuditAction.CONFIG_UPDATED.value == "config_updated"
        assert AuditAction.DATA_EXPORTED.value == "data_exported"


class TestIntegration:
    """Integration tests for auth system."""

    def setup_method(self):
        """Reset state before each test."""
        APIKeyAuth._keys = {}
        APIKeyAuth._usage = {}
        AuditLogger._logs = []

    def test_full_api_key_lifecycle(self):
        """Test complete API key lifecycle with audit logging."""
        # Create key
        raw_key, api_key = APIKeyAuth.create_key(
            name="Integration Test Key",
            role="admin",
            scopes=["broadcast:read", "broadcast:create"],
            created_by="test_admin"
        )

        # Log creation
        AuditLogger.log(
            action=AuditAction.API_KEY_CREATED,
            actor_id="test_admin",
            actor_role="super_admin",
            resource_type="api_key",
            resource_id=api_key.key_id,
            details={"name": "Integration Test Key", "role": "admin"}
        )

        # Use key
        verified = APIKeyAuth.verify_key(raw_key)
        assert verified is not None
        assert verified.key_id == api_key.key_id

        # Check permissions
        assert check_permission(verified.role, Permission.BROADCAST_READ) is True
        assert check_permission(verified.role, Permission.BROADCAST_CREATE) is True

        # Revoke key
        success = APIKeyAuth.revoke_key(api_key.key_id)
        assert success is True

        # Log revocation
        AuditLogger.log(
            action=AuditAction.API_KEY_REVOKED,
            actor_id="test_admin",
            actor_role="super_admin",
            resource_type="api_key",
            resource_id=api_key.key_id
        )

        # Verify key no longer works
        assert APIKeyAuth.verify_key(raw_key) is None

        # Check audit trail
        logs = AuditLogger.get_logs(resource_id=api_key.key_id)
        assert len(logs) == 2
        actions = [log["action"] for log in logs]
        assert "api_key_created" in actions
        assert "api_key_revoked" in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
