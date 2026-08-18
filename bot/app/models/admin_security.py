"""Typed authorization vocabulary for Phase 8.1 admin security."""

from __future__ import annotations

from enum import StrEnum


class AdminPrincipalStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    LOCKED = "locked"


class AdminRole(StrEnum):
    OWNER = "owner"
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATIONS = "operations"
    FINANCE = "finance"
    SUPPORT = "support"
    CONTENT_MANAGER = "content_manager"


class ActionSensitivity(StrEnum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class AdminChatPolicy(StrEnum):
    PRIVATE_ONLY = "private_only"
    APPROVED_CHATS = "approved_chats"
    ANY_CHAT_WITH_PERMISSION = "any_chat_with_permission"


class SecurityEventType(StrEnum):
    UNAUTHORIZED_ADMIN_ACCESS = "unauthorized_admin_access"
    FORGED_ADMIN_CALLBACK = "forged_admin_callback"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"
    ADMIN_CREATED = "admin_created"
    ADMIN_SUSPENDED = "admin_suspended"
    ADMIN_REVOKED = "admin_revoked"
    ADMIN_LOCKED = "admin_locked"
    ADMIN_ROLE_CHANGED = "admin_role_changed"
    ADMIN_PERMISSION_CHANGED = "admin_permission_changed"
    CRITICAL_ACTION_CONFIRMED = "critical_action_confirmed"
    CRITICAL_ACTION_EXECUTED = "critical_action_executed"


# These keys extend the original Phase 0 permission vocabulary without
# replacing it. The authorization service validates every requested key
# against this closed set before checking a principal's effective policy.
ADMIN_PERMISSION_KEYS = frozenset(
    {
        "manage_admins",
        "manage_roles",
        "manage_permissions",
        "view_audit",
        "manage_health",
        "manage_alerts",
        "manage_jobs",
        "manage_backups",
        "manage_maintenance",
        "manage_incidents",
        "manage_emergency",
        "adjust_wallet",
        "manage_servers",
        "manage_payments",
        "manage_users",
        "manage_promos",
        "manage_missions",
        "manage_referrals",
        "manage_rewards",
    }
)

ROLE_PERMISSION_POLICY: dict[str, frozenset[str]] = {
    AdminRole.OWNER.value: frozenset(ADMIN_PERMISSION_KEYS),
    AdminRole.SUPER_ADMIN.value: frozenset(ADMIN_PERMISSION_KEYS - {"manage_permissions"}),
    AdminRole.ADMIN.value: frozenset(
        {
            "manage_users",
            "manage_servers",
            "manage_payments",
            "manage_promos",
            "manage_missions",
            "manage_referrals",
            "manage_rewards",
            "view_audit",
        }
    ),
    AdminRole.OPERATIONS.value: frozenset(
        {
            "manage_health",
            "manage_alerts",
            "manage_jobs",
            "manage_backups",
            "manage_maintenance",
            "manage_incidents",
            "manage_emergency",
            "manage_servers",
            "view_audit",
        }
    ),
    AdminRole.FINANCE.value: frozenset({"manage_payments", "adjust_wallet", "view_audit"}),
    AdminRole.SUPPORT.value: frozenset({"manage_users", "view_audit"}),
    AdminRole.CONTENT_MANAGER.value: frozenset(
        {"manage_promos", "manage_missions", "manage_referrals", "manage_rewards"}
    ),
}

ROLE_RANK: dict[str, int] = {
    AdminRole.SUPPORT.value: 10,
    AdminRole.CONTENT_MANAGER.value: 20,
    AdminRole.OPERATIONS.value: 30,
    AdminRole.FINANCE.value: 30,
    AdminRole.ADMIN.value: 40,
    AdminRole.SUPER_ADMIN.value: 50,
    AdminRole.OWNER.value: 60,
}

CRITICAL_ACTIONS = frozenset(
    {
        "admin.grant_owner",
        "admin.grant_super_admin",
        "admin.revoke",
        "admin.lock",
        "admin.role_change",
        "admin.permission_change",
        "wallet.adjust",
        "maintenance.emergency_enable",
        "maintenance.force_exit",
        "backup.restore_prepare",
        "server.disable",
        "job.dead_letter_retry",
    }
)
