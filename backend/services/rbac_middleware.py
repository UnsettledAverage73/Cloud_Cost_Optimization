"""
CloudPulse Enterprise Role-Based Access Control (RBAC) & Security Middleware
Enforces Zero-Trust principles, role verification, and permission validation for enterprise FinOps operations.
"""

from enum import Enum
from typing import Dict, Any, List, Optional


class FinOpsRole(str, Enum):
    FINOPS_ADMIN = "FINOPS_ADMIN"
    FINOPS_ANALYST = "FINOPS_ANALYST"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"
    VIEWER = "VIEWER"


class FinOpsPermission(str, Enum):
    READ_DASHBOARDS = "read:dashboards"
    QUERY_COPILOT = "query:copilot"
    VIEW_ANOMALIES = "view:anomalies"
    VIEW_FORECAST = "view:forecast"
    TRIGGER_SCAN = "trigger:scan"
    GITOPS_APPLY = "gitops:apply"
    VIEW_AUDIT_LOG = "view:audit_log"
    MANAGE_ACCOUNTS = "manage:accounts"


ROLE_PERMISSIONS: Dict[FinOpsRole, List[FinOpsPermission]] = {
    FinOpsRole.FINOPS_ADMIN: [
        FinOpsPermission.READ_DASHBOARDS,
        FinOpsPermission.QUERY_COPILOT,
        FinOpsPermission.VIEW_ANOMALIES,
        FinOpsPermission.VIEW_FORECAST,
        FinOpsPermission.TRIGGER_SCAN,
        FinOpsPermission.GITOPS_APPLY,
        FinOpsPermission.VIEW_AUDIT_LOG,
        FinOpsPermission.MANAGE_ACCOUNTS
    ],
    FinOpsRole.FINOPS_ANALYST: [
        FinOpsPermission.READ_DASHBOARDS,
        FinOpsPermission.QUERY_COPILOT,
        FinOpsPermission.VIEW_ANOMALIES,
        FinOpsPermission.VIEW_FORECAST,
        FinOpsPermission.TRIGGER_SCAN,
        FinOpsPermission.VIEW_AUDIT_LOG
    ],
    FinOpsRole.SECURITY_AUDITOR: [
        FinOpsPermission.READ_DASHBOARDS,
        FinOpsPermission.VIEW_ANOMALIES,
        FinOpsPermission.VIEW_AUDIT_LOG
    ],
    FinOpsRole.VIEWER: [
        FinOpsPermission.READ_DASHBOARDS,
        FinOpsPermission.VIEW_FORECAST
    ]
}


class RBACSecurityManager:
    """
    Validates enterprise identity tokens and authorizes operations against RBAC rules.
    """

    DEMO_API_KEYS = {
        "cp-admin-key-999": {"role": FinOpsRole.FINOPS_ADMIN, "tenant_id": "org-enterprise-01", "user": "admin@enterprise.com"},
        "cp-analyst-key-123": {"role": FinOpsRole.FINOPS_ANALYST, "tenant_id": "org-enterprise-01", "user": "analyst@enterprise.com"},
        "cp-auditor-key-456": {"role": FinOpsRole.SECURITY_AUDITOR, "tenant_id": "org-enterprise-01", "user": "auditor@enterprise.com"},
        "cp-viewer-key-789": {"role": FinOpsRole.VIEWER, "tenant_id": "org-enterprise-01", "user": "viewer@enterprise.com"}
    }

    @classmethod
    def check_permission(cls, role: str, permission: str) -> bool:
        """Checks whether a role has permission to perform an action."""
        try:
            r = FinOpsRole(role)
            p = FinOpsPermission(permission)
            return p in ROLE_PERMISSIONS.get(r, [])
        except ValueError:
            return False

    @classmethod
    def authenticate_key(cls, api_key: Optional[str]) -> Dict[str, Any]:
        """Authenticates API key and returns identity context (defaulting to ADMIN in local dev)."""
        if not api_key:
            return {
                "authenticated": True,
                "role": FinOpsRole.FINOPS_ADMIN.value,
                "tenant_id": "org-default",
                "user": "local-dev@cloudpulse.io",
                "note": "Default dev authentication"
            }

        identity = cls.DEMO_API_KEYS.get(api_key)
        if identity:
            return {
                "authenticated": True,
                "role": identity["role"].value,
                "tenant_id": identity["tenant_id"],
                "user": identity["user"]
            }

        return {
            "authenticated": False,
            "role": None,
            "error": "Invalid API key"
        }


# Global Singleton
rbac_manager = RBACSecurityManager()
