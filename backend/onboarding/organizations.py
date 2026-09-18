import logging
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("cloudpulse.onboarding.organizations")

class OrganizationsDiscovery:
    """Discovers all member accounts under an AWS Organization Payer/Management account."""

    def __init__(self, session: boto3.Session = None):
        self.session = session or boto3.Session()
        self.client = self.session.client("organizations")

    def list_all_member_accounts(self) -> List[Dict[str, Any]]:
        """
        Discovers active accounts, returns account ID, name, email, and status.
        Handles pagination seamlessly.
        """
        accounts = []
        try:
            paginator = self.client.get_paginator("list_accounts")
            for page in paginator.paginate():
                for acc in page.get("Accounts", []):
                    if acc.get("Status") == "ACTIVE":
                        accounts.append({
                            "account_id": acc.get("Id"),
                            "account_name": acc.get("Name"),
                            "email": acc.get("Email"),
                            "status": acc.get("Status"),
                            "joined_method": acc.get("JoinedMethod"),
                            "arn": acc.get("Arn")
                        })
            logger.info(f"Discovered {len(accounts)} active AWS accounts in organization.")
            return accounts
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.warning(f"AWS Organizations query unavailable: [{error_code}] {e}")
            return []
