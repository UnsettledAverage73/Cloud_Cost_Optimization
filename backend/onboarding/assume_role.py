import boto3
import time
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger("cloudpulse.onboarding.assume_role")

class CrossAccountRoleManager:
    """
    Enterprise-grade AWS Cross-Account AssumeRole manager with ExternalId validation,
    session caching, and automatic credential refresh.
    Prevents the Confused Deputy problem.
    """
    def __init__(self, default_session_duration: int = 3600):
        self.session_duration = default_session_duration
        self._credential_cache: Dict[str, Dict[str, Any]] = {}

    def get_assumed_credentials(
        self,
        role_arn: str,
        external_id: str,
        session_name: str = "CloudPulseFinOpsSession",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Assumes the customer IAM role using ExternalId.
        Caches temporary credentials until 5 minutes prior to expiration.
        """
        cache_key = f"{role_arn}::{external_id}"
        now = time.time()

        if not force_refresh and cache_key in self._credential_cache:
            cached = self._credential_cache[cache_key]
            # Refresh if within 300 seconds of expiry
            if cached["expiration_timestamp"] > now + 300:
                return cached["credentials"]

        logger.info(f"Assuming role {role_arn} with ExternalId security validation...")
        sts_client = boto3.client("sts")

        try:
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                ExternalId=external_id,
                DurationSeconds=self.session_duration
            )

            creds = response["Credentials"]
            expiration = creds["Expiration"].timestamp()

            clean_creds = {
                "aws_access_key_id": creds["AccessKeyId"],
                "aws_secret_access_key": creds["SecretAccessKey"],
                "aws_session_token": creds["SessionToken"]
            }

            self._credential_cache[cache_key] = {
                "credentials": clean_creds,
                "expiration_timestamp": expiration
            }

            return clean_creds

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Failed to assume role {role_arn}: [{error_code}] {error_msg}")
            raise PermissionError(f"Cross-account AssumeRole failed: [{error_code}] {error_msg}")

    def create_boto3_session(
        self,
        role_arn: str,
        external_id: str,
        region_name: str = "us-east-1"
    ) -> boto3.Session:
        """Returns a boto3.Session authenticated via the cross-account role."""
        creds = self.get_assumed_credentials(role_arn=role_arn, external_id=external_id)
        return boto3.Session(
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"],
            region_name=region_name
        )

    def validate_connection(self, role_arn: str, external_id: str) -> Dict[str, Any]:
        """
        Validates the IAM trust relationship by invoking sts:GetCallerIdentity.
        Returns account metadata or diagnostic error details.
        """
        try:
            session = self.create_boto3_session(role_arn=role_arn, external_id=external_id)
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            return {
                "valid": True,
                "target_account_id": identity["Account"],
                "caller_arn": identity["Arn"],
                "user_id": identity["UserId"],
                "error": None
            }
        except Exception as e:
            logger.warning(f"Validation failed for role {role_arn}: {e}")
            return {
                "valid": False,
                "target_account_id": None,
                "caller_arn": None,
                "error": str(e)
            }
