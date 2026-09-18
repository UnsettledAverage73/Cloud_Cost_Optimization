import socket
import urllib.request
import json
import logging
import uuid
import os
import platform

logger = logging.getLogger("cloudpulse.agent.detector")

class CloudInstanceDetector:
    """
    Detects whether the agent is running on AWS EC2, Microsoft Azure, Google Cloud (GCP),
    or on-premise/local infrastructure, extracting native instance metadata.
    """

    @staticmethod
    def _make_http_get(url: str, headers: dict = None, timeout: float = 0.5) -> str:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8").strip()

    @classmethod
    def detect_aws(cls) -> dict:
        """Attempts IMDSv2 query on AWS."""
        try:
            # 1. Fetch IMDSv2 Session Token
            token_req = urllib.request.Request(
                "http://169.254.169.254/latest/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
                method="PUT"
            )
            with urllib.request.urlopen(token_req, timeout=0.5) as resp:
                token = resp.read().decode("utf-8").strip()

            auth_header = {"X-aws-ec2-metadata-token": token}
            instance_id = cls._make_http_get("http://169.254.169.254/latest/meta-data/instance-id", headers=auth_header)
            instance_type = cls._make_http_get("http://169.254.169.254/latest/meta-data/instance-type", headers=auth_header)
            az = cls._make_http_get("http://169.254.169.254/latest/meta-data/placement/availability-zone", headers=auth_header)
            region = az[:-1] if az else "us-east-1"

            return {
                "detected": True,
                "provider": "aws",
                "instance_id": instance_id,
                "instance_type": instance_type,
                "region": region,
                "availability_zone": az
            }
        except Exception:
            return {"detected": False}

    @classmethod
    def detect_azure(cls) -> dict:
        """Attempts Azure IMDS query."""
        try:
            url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
            res = cls._make_http_get(url, headers={"Metadata": "true"}, timeout=0.5)
            data = json.loads(res)
            compute = data.get("compute", {})
            return {
                "detected": True,
                "provider": "azure",
                "instance_id": compute.get("vmId"),
                "instance_type": compute.get("vmSize"),
                "region": compute.get("location"),
                "availability_zone": compute.get("zone")
            }
        except Exception:
            return {"detected": False}

    @classmethod
    def detect_gcp(cls) -> dict:
        """Attempts GCP Metadata query."""
        try:
            url = "http://metadata.google.internal/computeMetadata/v1/instance/?recursive=true"
            res = cls._make_http_get(url, headers={"Metadata-Flavor": "Google"}, timeout=0.5)
            data = json.loads(res)
            return {
                "detected": True,
                "provider": "gcp",
                "instance_id": str(data.get("id")),
                "instance_type": data.get("machineType", "").split("/")[-1],
                "region": data.get("zone", "").split("/")[-1],
                "availability_zone": data.get("zone", "").split("/")[-1]
            }
        except Exception:
            return {"detected": False}

    @classmethod
    def detect(cls) -> dict:
        """Auto-detects cloud provider environment or falls back to local machine identity."""
        # 1. Check AWS
        aws = cls.detect_aws()
        if aws["detected"]:
            return aws

        # 2. Check Azure
        azure = cls.detect_azure()
        if azure["detected"]:
            return azure

        # 3. Check GCP
        gcp = cls.detect_gcp()
        if gcp["detected"]:
            return gcp

        # 4. Fallback to Local Host / On-Prem
        host_name = socket.gethostname()
        local_id = f"host-{uuid.uuid5(uuid.NAMESPACE_DNS, host_name).hex[:12]}"
        return {
            "detected": True,
            "provider": "on-premise",
            "instance_id": local_id,
            "instance_type": f"bare-metal-{platform.machine()}",
            "region": "local",
            "availability_zone": "local-datacenter"
        }
