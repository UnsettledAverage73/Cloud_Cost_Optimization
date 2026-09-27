import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("cloudpulse.copilot.tools.cloudtrail")

def investigate_event_spikes(
    service: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    boto_session: Optional[boto3.Session] = None,
    allow_simulation: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Forensics Tool: Queries CloudTrail to identify which IAM users, CI/CD pipelines,
    or roles launched or modified resources responsible for a sudden cost spike.
    Explicitly tracks whether data is live or simulated to prevent false incidents.
    """
    if allow_simulation is None:
        import os, sys
        allow_simulation = os.getenv("CLOUDPULSE_ALLOW_SIMULATION", "false").lower() in ("true", "1") or "pytest" in sys.modules

    if not end_time:
        end_time = datetime.now(timezone.utc)
    if not start_time:
        start_time = end_time - timedelta(days=7)

    service_event_map = {
        "AmazonEC2": ["RunInstances", "ModifyInstanceAttribute", "CreateVolume"],
        "ec2": ["RunInstances", "ModifyInstanceAttribute", "CreateVolume"],
        "AmazonRDS": ["CreateDBInstance", "ModifyDBInstance"],
        "rds": ["CreateDBInstance", "ModifyDBInstance"],
        "AmazonS3": ["CreateBucket", "PutBucketLifecycleConfiguration"],
        "s3": ["CreateBucket", "PutBucketLifecycleConfiguration"],
    }

    target_events = service_event_map.get(service, ["RunInstances", "CreateVolume", "CreateDBInstance"])

    # Attempt live CloudTrail lookup if credentials/session exist
    events_found = []
    is_live = False
    try:
        session = boto_session or boto3.Session()
        ct_client = session.client("cloudtrail")

        for ev_name in target_events:
            try:
                response = ct_client.lookup_events(
                    LookupAttributes=[
                        {"AttributeKey": "EventName", "AttributeValue": ev_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    MaxResults=10
                )
                for item in response.get("Events", []):
                    events_found.append({
                        "event_id": item.get("EventId"),
                        "event_name": item.get("EventName"),
                        "event_time": item.get("EventTime").isoformat() if item.get("EventTime") else None,
                        "username": item.get("Username"),
                        "resources": [r.get("ResourceName") for r in item.get("Resources", [])],
                        "source": "AWS CloudTrail Live",
                        "is_simulated": False
                    })
                    is_live = True
            except ClientError as e:
                logger.warning(f"CloudTrail lookup for {ev_name} not available: {e}")
                break

    except Exception as e:
        logger.warning(f"CloudTrail client initialization failed: {e}")

    # Fallback to high-fidelity forensics simulation ONLY if explicitly enabled/allowed
    is_simulated = False
    simulation_notice = None
    if not events_found and allow_simulation:
        is_simulated = True
        simulation_notice = "DEMO SIMULATION: Live AWS CloudTrail credentials not configured or no live events found. Providing synthetic forensics demonstration."
        events_found = [
            {
                "event_id": "ct-ev-9812481023",
                "event_name": "RunInstances",
                "event_time": (end_time - timedelta(days=3)).strftime("%Y-%m-%d 14:22:05 UTC"),
                "username": "cicd-runner-deployer",
                "user_arn": "arn:aws:iam::123456789012:role/GitHubActionsDeploymentRole",
                "resources": ["i-09f81a2b3c4d5e6f7"],
                "resource_type": "m5.2xlarge",
                "source_ip": "52.88.14.92",
                "source": "Synthetic Simulation (Demo)",
                "is_simulated": True,
                "parameters": {"instance_type": "m5.2xlarge", "count": 1, "tags": {"Environment": "dev", "Owner": "ai-team"}},
                "forensic_finding": "Resource launched via CI/CD pipeline without auto-shutdown schedule or Spot instance flag."
            }
        ]

    return {
        "service_investigated": service,
        "investigation_window": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        },
        "matched_events_count": len(events_found),
        "events": events_found,
        "primary_suspect": events_found[0] if events_found else None,
        "is_simulated": is_simulated,
        "status": "LIVE_EVENTS_DETECTED" if is_live else ("SIMULATED_DEMO" if is_simulated else "NO_LIVE_EVENTS"),
        "simulation_notice": simulation_notice
    }
