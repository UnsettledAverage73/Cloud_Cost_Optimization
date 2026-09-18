import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
try:
    from database.models import Organization, ConnectedAWSAccount
    from onboarding.assume_role import CrossAccountRoleManager
except ImportError:
    from backend.database.models import Organization, ConnectedAWSAccount
    from backend.onboarding.assume_role import CrossAccountRoleManager

logger = logging.getLogger("cloudpulse.onboarding.tenant_manager")

class TenantManager:
    """Manages multi-tenant organization provisioning and AWS account lifecycle."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.role_manager = CrossAccountRoleManager()

    def create_organization(self, name: str, plan_tier: str = "enterprise") -> Organization:
        org = Organization(name=name, plan_tier=plan_tier)
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def register_aws_account(
        self,
        organization_id: str,
        account_id: str,
        account_name: str,
        role_arn: str,
        external_id: str,
        regions: List[str] = None,
        validate_immediately: bool = True
    ) -> Dict[str, Any]:
        """Registers a new AWS account for an organization and validates STS credentials."""
        regions = regions or ["us-east-1"]

        status = "pending"
        validation_error = None

        if validate_immediately:
            validation = self.role_manager.validate_connection(role_arn=role_arn, external_id=external_id)
            if validation["valid"]:
                status = "active"
            else:
                status = "error"
                validation_error = validation["error"]

        org_uuid = uuid.UUID(organization_id)
        existing = self.db.query(ConnectedAWSAccount).filter_by(
            organization_id=org_uuid,
            account_id=account_id
        ).first()

        if existing:
            existing.account_name = account_name
            existing.role_arn = role_arn
            existing.external_id = external_id
            existing.regions = regions
            existing.status = status
            self.db.commit()
            self.db.refresh(existing)
            result = existing.to_dict()
            if validation_error:
                result["validation_error"] = validation_error
            return result

        account = ConnectedAWSAccount(
            organization_id=org_uuid,
            account_id=account_id,
            account_name=account_name,
            role_arn=role_arn,
            external_id=external_id,
            auth_method="assume_role",
            regions=regions,
            status=status
        )

        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)

        result = account.to_dict()
        if validation_error:
            result["validation_error"] = validation_error
        return result

    def get_accounts_for_org(self, organization_id: str) -> List[Dict[str, Any]]:
        accounts = self.db.query(ConnectedAWSAccount).filter_by(
            organization_id=uuid.UUID(organization_id)
        ).all()
        return [acc.to_dict() for acc in accounts]

    def test_account_connection(self, account_id: str) -> Dict[str, Any]:
        account = self.db.query(ConnectedAWSAccount).filter_by(id=uuid.UUID(account_id)).first()
        if not account:
            return {"valid": False, "error": "Account not found"}

        res = self.role_manager.validate_connection(
            role_arn=account.role_arn,
            external_id=account.external_id
        )
        if res["valid"]:
            account.status = "active"
        else:
            account.status = "error"
        self.db.commit()
        return res
