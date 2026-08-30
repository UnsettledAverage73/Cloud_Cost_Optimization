import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import json
import mock_database
from schemas import IngestionPayload, CloudConnectRequest, NodeSchema

app = FastAPI(
    title="CloudPulse FinOps & Telemetry API",
    version="1.0.0",
    description="Backend API powering multi-cloud cost optimization & telemetry dashboards."
)

# Enable CORS for Next.js / React / v0.dev frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active session credentials (or pass per header/request)
active_credentials = {}
connected_accounts = []
last_live_error = ""
STATE_FILE = Path(__file__).with_name(".cloudpulse_state.json")

AWS_CLIENT_CONFIG = Config(
    connect_timeout=3,
    read_timeout=8,
    retries={"max_attempts": 1, "mode": "standard"},
)

_INSTANCE_MONTHLY_RATES = {
    "t3.nano": 3.80,
    "t3.micro": 7.60,
    "t3.small": 15.20,
    "t3.medium": 30.40,
    "t3.large": 60.80,
}


def _load_persisted_state():
    global active_credentials, connected_accounts

    if not STATE_FILE.exists():
        return

    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        return

    active = state.get("active_connection")
    if isinstance(active, dict) and active:
        active_credentials["default"] = active

    accounts = state.get("connected_accounts", [])
    if isinstance(accounts, list):
        connected_accounts[:] = [item for item in accounts if isinstance(item, dict)]


def _persist_state():
    state = {
        "active_connection": active_credentials.get("default"),
        "connected_accounts": connected_accounts,
    }
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
    except Exception:
        pass


_load_persisted_state()


def _connection_signature(payload: dict) -> tuple:
    return (
        (payload.get("provider") or "").lower(),
        (payload.get("account_name") or "").strip().lower(),
        (payload.get("region") or "").strip().lower(),
        (payload.get("role_arn") or "").strip().lower(),
        (payload.get("access_key") or "").strip()[-4:],
    )


def _public_connection_record(payload: dict) -> dict:
    return {
        "provider": payload.get("provider"),
        "account_name": payload.get("account_name"),
        "auth_method": payload.get("auth_method"),
        "role_arn": payload.get("role_arn"),
        "region": payload.get("region"),
        "connected_at": payload.get("connected_at"),
        "active": payload.get("active", False),
        "access_key_last4": payload.get("access_key_last4"),
        "session_token_present": bool(payload.get("session_token")),
    }


def _set_connection_mode(access_mode: str, warning: str | None = None):
    if not active_credentials.get("default"):
        return
    active_credentials["default"]["access_mode"] = access_mode
    if warning:
        active_credentials["default"]["warning"] = warning
    elif "warning" in active_credentials["default"]:
        active_credentials["default"].pop("warning", None)
    _persist_state()


def _save_active_credentials(credentials: CloudConnectRequest):
    profile = {
        "provider": credentials.provider,
        "account_name": credentials.account_name,
        "auth_method": credentials.auth_method,
        "access_key": credentials.access_key,
        "secret_key": credentials.secret_key,
        "session_token": credentials.session_token,
        "role_arn": credentials.role_arn,
        "region": credentials.region,
    }
    active_credentials["default"] = profile

    profile_key = (
        credentials.provider.lower(),
        (credentials.account_name or "").strip().lower(),
        (credentials.region or "").strip().lower(),
        (credentials.role_arn or "").strip().lower(),
        (credentials.access_key or "").strip()[-4:],
    )

    existing_index = next(
        (
            idx
            for idx, item in enumerate(connected_accounts)
            if (
                item.get("provider", "").lower(),
                item.get("account_name", "").strip().lower(),
                item.get("region", "").strip().lower(),
                item.get("role_arn", "").strip().lower(),
                item.get("access_key_last4", ""),
            ) == profile_key
        ),
        None,
    )

    connected_record = {
        "provider": credentials.provider,
        "account_name": credentials.account_name,
        "auth_method": credentials.auth_method,
        "access_key": credentials.access_key,
        "secret_key": credentials.secret_key,
        "session_token": credentials.session_token,
        "role_arn": credentials.role_arn,
        "region": credentials.region,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "access_key_last4": (credentials.access_key or "").strip()[-4:] or None,
        "session_token_present": bool(credentials.session_token),
    }

    if existing_index is not None:
        for idx, item in enumerate(connected_accounts):
            item["active"] = idx == existing_index
        connected_accounts[existing_index] = {**connected_accounts[existing_index], **connected_record}
    else:
        for item in connected_accounts:
            item["active"] = False
        connected_accounts.append(connected_record)

    _persist_state()


def _saved_credentials():
    return active_credentials.get("default")


def _connection_state():
    creds = _saved_credentials()
    if not creds:
        return {
            "connected": False,
            "provider": None,
            "account_name": None,
            "region": None,
            "access_mode": None,
            "warning": None,
            "connected_accounts": [_public_connection_record(item) for item in connected_accounts],
        }
    return {
        "connected": True,
        "provider": creds.get("provider"),
        "account_name": creds.get("account_name"),
        "region": creds.get("region"),
        "auth_method": creds.get("auth_method"),
        "role_arn": creds.get("role_arn"),
        "access_mode": creds.get("access_mode", "live"),
        "warning": creds.get("warning"),
        "connected_accounts": [_public_connection_record(item) for item in connected_accounts],
    }


def _estimate_instance_monthly_cost(instance_type: str) -> float:
    return _INSTANCE_MONTHLY_RATES.get(instance_type, 10.00)


def _estimate_ebs_monthly_cost(volume: dict) -> float:
    volume_type = (volume.get("volume_type") or volume.get("VolumeType") or "gp3").lower()
    size_gb = volume.get("size_gb") or volume.get("Size") or 0
    rate = 0.08 if volume_type.startswith("gp3") else 0.10 if volume_type.startswith("gp2") else 0.12
    return round(float(size_gb) * rate, 2)


def _build_aws_session():
    creds = _saved_credentials()
    if not creds or creds.get("provider", "").upper() != "AWS":
        return None

    session_kwargs = {
        "region_name": creds.get("region", "us-east-1"),
    }
    if creds.get("access_key"):
        session_kwargs["aws_access_key_id"] = creds["access_key"]
    if creds.get("secret_key"):
        session_kwargs["aws_secret_access_key"] = creds["secret_key"]
    if creds.get("session_token"):
        session_kwargs["aws_session_token"] = creds["session_token"]

    return boto3.Session(**session_kwargs)


def _activate_connected_account(selector: dict) -> dict:
    target_signature = _connection_signature(selector)
    match = next(
        (
            item
            for item in connected_accounts
            if _connection_signature(item) == target_signature
        ),
        None,
    )

    if not match:
        raise HTTPException(status_code=404, detail="Saved AWS account not found.")

    if not (match.get("access_key") and match.get("secret_key")):
        raise HTTPException(status_code=400, detail="Saved account does not include credentials required to reconnect.")

    for item in connected_accounts:
        item["active"] = _connection_signature(item) == target_signature

    active_credentials["default"] = {
        "provider": match.get("provider"),
        "account_name": match.get("account_name"),
        "auth_method": match.get("auth_method"),
        "access_key": match.get("access_key"),
        "secret_key": match.get("secret_key"),
        "session_token": match.get("session_token"),
        "role_arn": match.get("role_arn"),
        "region": match.get("region"),
    }
    _persist_state()
    return match


def _is_permission_denied(error_message: str) -> bool:
    lowered = (error_message or "").lower()
    return (
        "unauthorizedoperation" in lowered
        or "accessdenied" in lowered
        or "explicit deny" in lowered
        or "not authorized to perform" in lowered
    )


def _tag_lookup(tags):
    return {tag.get("Key"): tag.get("Value") for tag in tags or []}


def _optional_pages(client, operation):
    """Return no data when a Learner Lab denies an optional inventory API."""
    try:
        return list(client.get_paginator(operation).paginate())
    except (ClientError, BotoCoreError):
        return []


def _optional_call(client, operation, **kwargs):
    """Run an optional AWS API without breaking Learner Lab onboarding."""
    try:
        return getattr(client, operation)(**kwargs)
    except (ClientError, BotoCoreError):
        return {}


def _refresh_live_aws_state():
    global last_live_error
    session = _build_aws_session()
    if not session:
        last_live_error = "No AWS session is configured."
        return False

    try:
        ec2 = session.client("ec2", config=AWS_CLIENT_CONFIG)
        region = session.region_name or "us-east-1"
        db = _db()

        nodes = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    tags = _tag_lookup(instance.get("Tags"))
                    instance_type = instance.get("InstanceType", "unknown")
                    block_devices = instance.get("BlockDeviceMappings", [])
                    nodes.append(
                        {
                            "instance_id": instance["InstanceId"],
                            "name": tags.get("Name") or instance["InstanceId"],
                            "instance_type": instance_type,
                            "state": instance.get("State", {}).get("Name", "unknown"),
                            "platform": "windows" if instance.get("Platform") == "windows" else "linux",
                            "availability_zone": instance.get("Placement", {}).get("AvailabilityZone", region),
                            "region": region,
                            "public_ip": instance.get("PublicIpAddress"),
                            "volumes": len(block_devices),
                            "cost": _estimate_instance_monthly_cost(instance_type),
                        }
                    )

        volumes = []
        for page in _optional_pages(ec2, "describe_volumes"):
            for volume in page.get("Volumes", []):
                attachments = volume.get("Attachments", [])
                volumes.append(
                    {
                        "volume_id": volume["VolumeId"],
                        "size_gb": volume.get("Size", 0),
                        "volume_type": volume.get("VolumeType", "gp3"),
                        "iops": volume.get("Iops", 3000),
                        "status": volume.get("State", "unknown"),
                        "is_orphaned": len(attachments) == 0,
                        "attached_instance_id": attachments[0].get("InstanceId") if attachments else None,
                        "attachments": attachments,
                        "cost": _estimate_ebs_monthly_cost(volume),
                    }
                )

        elastic_ips = []
        for page in _optional_pages(ec2, "describe_addresses"):
            for address in page.get("Addresses", []):
                elastic_ips.append(
                    {
                        "public_ip": address.get("PublicIp", ""),
                        "is_unattached": not address.get("InstanceId"),
                        "estimated_monthly_cost": 3.60,
                    }
                )

        security_groups = []
        for page in _optional_pages(ec2, "describe_security_groups"):
            for group in page.get("SecurityGroups", []):
                exposed_ports = []
                is_public = False
                for permission in group.get("IpPermissions", []):
                    public_cidrs = any(r.get("CidrIp") == "0.0.0.0/0" for r in permission.get("IpRanges", []))
                    public_ipv6 = any(r.get("CidrIpv6") == "::/0" for r in permission.get("Ipv6Ranges", []))
                    if not (public_cidrs or public_ipv6):
                        continue

                    is_public = True
                    from_port = permission.get("FromPort")
                    to_port = permission.get("ToPort")
                    if isinstance(from_port, int):
                        exposed_ports.append(from_port)
                    if isinstance(to_port, int) and to_port != from_port:
                        exposed_ports.append(to_port)

                security_groups.append(
                    {
                        "group_id": group["GroupId"],
                        "group_name": group.get("GroupName", group["GroupId"]),
                        "is_publicly_exposed": is_public,
                        "exposed_ports": sorted(set(exposed_ports)),
                    }
                )

        # Additional inventory collected by the notebook. These APIs are optional
        # because Learner Lab permission boundaries may deny some of them.
        amis = []
        for image in _optional_call(ec2, "describe_images", Owners=["self"]).get("Images", []):
            snapshots = [
                mapping["Ebs"]["SnapshotId"]
                for mapping in image.get("BlockDeviceMappings", [])
                if mapping.get("Ebs", {}).get("SnapshotId")
            ]
            amis.append({
                "ami_id": image.get("ImageId"),
                "name": image.get("Name"),
                "creation_date": image.get("CreationDate"),
                "snapshot_ids": snapshots,
                "architecture": image.get("Architecture"),
            })

        network_interfaces = []
        for eni in _optional_call(ec2, "describe_network_interfaces").get("NetworkInterfaces", []):
            attachment = eni.get("Attachment") or {}
            association = eni.get("Association") or {}
            network_interfaces.append({
                "network_interface_id": eni.get("NetworkInterfaceId"),
                "status": eni.get("Status"),
                "is_orphaned": eni.get("Status") == "available",
                "attached_instance_id": attachment.get("InstanceId"),
                "private_ip": eni.get("PrivateIpAddress"),
                "public_ip": association.get("PublicIp"),
            })

        ebs_snapshots = []
        for snapshot in _optional_call(ec2, "describe_snapshots", OwnerIds=["self"]).get("Snapshots", []):
            size_gb = snapshot.get("VolumeSize", 0)
            start_time = snapshot.get("StartTime")
            ebs_snapshots.append({
                "snapshot_id": snapshot.get("SnapshotId"),
                "volume_id": snapshot.get("VolumeId"),
                "size_gb": size_gb,
                "start_time": start_time.isoformat() if start_time else None,
                "estimated_monthly_cost": round(size_gb * 0.05, 2),
            })

        logs = session.client("logs", config=AWS_CLIENT_CONFIG)
        cloudwatch_log_groups = []
        for page in _optional_pages(logs, "describe_log_groups"):
            for group in page.get("logGroups", []):
                stored_bytes = group.get("storedBytes", 0)
                retention = group.get("retentionInDays")
                cloudwatch_log_groups.append({
                    "log_group_name": group.get("logGroupName"),
                    "stored_bytes": stored_bytes,
                    "stored_gb": round(stored_bytes / (1024 ** 3), 3),
                    "retention_in_days": retention,
                    "is_never_expire": retention is None,
                    "estimated_monthly_cost": round((stored_bytes / (1024 ** 3)) * 0.03, 2),
                })

        s3 = session.client("s3", config=AWS_CLIENT_CONFIG)
        s3_buckets = []
        for bucket in _optional_call(s3, "list_buckets").get("Buckets", []):
            bucket_name = bucket.get("Name")
            lifecycle = _optional_call(s3, "get_bucket_lifecycle_configuration", Bucket=bucket_name)
            s3_buckets.append({
                "bucket_name": bucket_name,
                "creation_date": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None,
                "has_lifecycle_policy": bool(lifecycle),
            })

        nat_gateways = []
        for page in _optional_pages(ec2, "describe_nat_gateways"):
            for nat in page.get("NatGateways", []):
                if nat.get("State") in ["available", "pending"]:
                    nat_gateways.append({
                        "nat_gateway_id": nat.get("NatGatewayId"),
                        "vpc_id": nat.get("VpcId"),
                        "subnet_id": nat.get("SubnetId"),
                        "state": nat.get("State"),
                        "estimated_monthly_base_cost": 32.40,
                    })

        vpc_endpoints = []
        for endpoint in _optional_call(ec2, "describe_vpc_endpoints").get("VpcEndpoints", []):
            vpc_endpoints.append({
                "vpc_endpoint_id": endpoint.get("VpcEndpointId"),
                "vpc_id": endpoint.get("VpcId"),
                "service_name": endpoint.get("ServiceName"),
                "endpoint_type": endpoint.get("VpcEndpointType"),
                "state": endpoint.get("State"),
                "estimated_monthly_base_cost": 7.20,
            })

        db["nodes"] = nodes
        db["ebs_volumes"] = volumes
        db["elastic_ips"] = elastic_ips
        db["security_groups"] = security_groups
        db["amis"] = amis
        db["network_interfaces"] = network_interfaces
        db["ebs_snapshots"] = ebs_snapshots
        db["cloudwatch_log_groups"] = cloudwatch_log_groups
        db["s3_buckets"] = s3_buckets
        db["vpc_resources"] = {"nat_gateways": nat_gateways, "vpc_endpoints": vpc_endpoints}
        db["metadata"]["region"] = region
        db["metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        saved = _saved_credentials() or {}
        db["metadata"]["organization"] = saved.get("account_name", db["metadata"].get("organization", "Acme Corp"))
        return True
    except (ClientError, BotoCoreError) as error:
        if isinstance(error, ClientError):
            error_data = error.response.get("Error", {})
            last_live_error = f"{error_data.get('Code', 'AWS error')}: {error_data.get('Message', str(error))}"
        else:
            last_live_error = f"{type(error).__name__}: {error}"
        return False
    except Exception as error:
        last_live_error = f"{type(error).__name__}: {error}"
        return False


def _ensure_live_aws_state():
    """Fail closed so dashboard APIs never serve seed data as live data."""
    if not _build_aws_session():
        raise HTTPException(status_code=401, detail="Connect an AWS account before loading live data.")
    if not _refresh_live_aws_state():
        if _is_permission_denied(last_live_error):
            return
        raise HTTPException(status_code=502, detail=f"AWS data refresh failed: {last_live_error}")


def _db():
    return mock_database.DB


def _node_volume_count(node: dict) -> int:
    return int(node.get("volumes") or 1)


def _frontend_nodes(status: Optional[str] = None, search: Optional[str] = None):
    _ensure_live_aws_state()
    db = _db()
    region = db["metadata"].get("region", "us-east-1")
    nodes = []
    for node in db["nodes"]:
        normalized = {
            **node,
            "region": region,
            "volumes": _node_volume_count(node),
        }
        if status and normalized["state"].lower() != status.lower():
            continue
        if search and search.lower() not in normalized["instance_id"].lower() and search.lower() not in normalized["name"].lower():
            continue
        nodes.append(normalized)
    return nodes


def _normalize_node(node: dict):
    db = _db()
    region = db["metadata"].get("region", "us-east-1")
    return {
        **node,
        "region": region,
        "volumes": _node_volume_count(node),
    }


def _normalize_telemetry_points():
    points = []
    for item in _db()["telemetry"]:
        points.append(
            {
                "time": item["timestamp"],
                "cpu": item["cpu_utilization"],
                "mem": item["mem_used_percent"],
                "netIn": item.get("net_in_mb", 0),
                "netOut": item.get("net_out_mb", 0),
                "read": round(item.get("net_in_mb", 0) * 0.08, 2),
                "write": round(item.get("net_out_mb", 0) * 0.06, 2),
            }
        )
    return points


def _live_instance_telemetry(instance_id: str, timeframe: str = "24h"):
    session = _build_aws_session()
    if not session:
        return None

    try:
        cloudwatch = session.client("cloudwatch", config=AWS_CLIENT_CONFIG)
        hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(timeframe, 24)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        period = 3600

        def fetch_metric(metric_name: str):
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average"],
            )
            return sorted(response.get("Datapoints", []), key=lambda point: point["Timestamp"])

        cpu_points = fetch_metric("CPUUtilization")
        net_in_points = fetch_metric("NetworkIn")
        net_out_points = fetch_metric("NetworkOut")

        timeline = {}

        for point in cpu_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["cpu"] = round(point.get("Average", 0), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        for point in net_in_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["netIn"] = round(point.get("Average", 0) / (1024 * 1024), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        for point in net_out_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["netOut"] = round(point.get("Average", 0) / (1024 * 1024), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        values = []
        for _, point in sorted(timeline.items(), key=lambda item: item[0]):
            cpu = point.get("cpu", 0)
            net_in = point.get("netIn", 0)
            net_out = point.get("netOut", 0)
            values.append(
                {
                    "time": point["time"],
                    "cpu": cpu,
                    "mem": 0,
                    "netIn": net_in,
                    "netOut": net_out,
                    "read": round(net_in * 0.08, 2),
                    "write": round(net_out * 0.06, 2),
                }
            )

        return values
    except (ClientError, BotoCoreError):
        return None


def _frontend_telemetry(timeframe: str = "24h"):
    _ensure_live_aws_state()
    first_node = _db()["nodes"][0] if _db()["nodes"] else None
    if not first_node:
        return []
    live = _live_instance_telemetry(first_node["instance_id"], timeframe)
    return live or []


def _frontend_spend():
    _ensure_live_aws_state()
    try:
        cost = _build_aws_session().client("ce", config=AWS_CLIENT_CONFIG)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=30)
        response = cost.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
        return [
            {
                "day": item["TimePeriod"]["Start"],
                "aws": round(float(item["Total"].get("UnblendedCost", {}).get("Amount", 0)), 2),
                "gcp": 0,
                "azure": 0,
            }
            for item in response.get("ResultsByTime", [])
        ]
    except (ClientError, BotoCoreError):
        # Cost Explorer is commonly disabled in Learner Labs. Billing data is optional.
        return []


def _frontend_alerts():
    _ensure_live_aws_state()
    db = _db()
    alerts = []

    for sg in db["security_groups"]:
        if sg["is_publicly_exposed"]:
            alerts.append(
                {
                    "id": f"sg-{sg['group_id']}",
                    "title": f"Public security group: {sg['group_name']}",
                    "desc": f"Ports {', '.join(map(str, sg['exposed_ports']))} are exposed to the internet.",
                    "tone": "red",
                    "tag": "Security",
                }
            )

    for eip in db["elastic_ips"]:
        if eip["is_unattached"]:
            alerts.append(
                {
                    "id": f"eip-{eip['public_ip']}",
                    "title": f"Unattached Elastic IP {eip['public_ip']}",
                    "desc": "Release the address to stop paying idle public IP charges.",
                    "tone": "amber",
                    "tag": "Cost",
                }
            )

    for vol in db["ebs_volumes"]:
        if vol.get("is_orphaned"):
            alerts.append(
                {
                    "id": f"vol-{vol['volume_id']}",
                    "title": f"Orphaned EBS volume {vol['volume_id']}",
                    "desc": "Volume is detached and can likely be deleted after validation.",
                    "tone": "amber",
                    "tag": "Storage",
                }
            )

    return alerts


def _frontend_optimizations():
    _ensure_live_aws_state()
    db = _db()
    recommendations = []

    for eip in db["elastic_ips"]:
        if eip["is_unattached"]:
            recommendations.append(
                {
                    "id": f"rec-eip-{eip['public_ip']}",
                    "type": "Orphaned Resource",
                    "title": f"Release unattached Elastic IP ({eip['public_ip']})",
                    "desc": "Idle public IPs generate avoidable hourly charges.",
                    "save": f"${eip['estimated_monthly_cost']:.2f}/mo",
                }
            )

    for vol in db["ebs_volumes"]:
        if vol.get("is_orphaned"):
            recommendations.append(
                {
                    "id": f"rec-vol-{vol['volume_id']}",
                    "type": "Idle Storage",
                    "title": f"Delete unattached EBS volume ({vol['volume_id']})",
                    "desc": "Detached volumes are billing without supporting workloads.",
                    "save": f"${vol.get('cost', 8.0):.2f}/mo",
                }
            )

    return recommendations

# --- 1. INGESTION ENDPOINT (From Python Engine) ---
@app.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_cloud_data(payload: IngestionPayload):
    """
    Receives raw output from your OptiScale Python script and updates DB state.
    """
    db = mock_database.DB
    db["metadata"] = payload.metadata
    db["nodes"] = payload.compute.get("nodes", [])
    db["ebs_volumes"] = payload.ec2_other_resources.get("ebs_volumes", [])
    db["elastic_ips"] = payload.ec2_other_resources.get("elastic_ips", [])
    db["security_groups"] = payload.ec2_other_resources.get("security_groups", [])
    db["telemetry"] = [t.dict() for t in payload.telemetry]
    
    return {"status": "success", "message": "Telemetry and resource data ingested successfully"}

# --- 2. EXECUTIVE OVERVIEW API ---
@app.get("/api/v1/dashboard/summary")
async def get_executive_summary():
    _ensure_live_aws_state()
    db = mock_database.DB
    total_nodes = len(db["nodes"])
    running_nodes = sum(1 for n in db["nodes"] if n["state"] == "running")
    
    # Calculate costs and wastes
    spend_rows = _frontend_spend()
    monthly_spend = sum(row.get("aws", 0) for row in spend_rows)
    wasted_eip = sum(eip["estimated_monthly_cost"] for eip in db["elastic_ips"] if eip["is_unattached"])
    wasted_ebs = sum(v["cost"] for v in db["ebs_volumes"] if v.get("is_orphaned"))
    total_wasted = wasted_eip + wasted_ebs

    critical_security_risks = sum(1 for sg in db["security_groups"] if sg["is_publicly_exposed"])

    return {
        "monthly_spend": round(monthly_spend, 2),
        "total_nodes": total_nodes,
        "running_nodes": running_nodes,
        "stopped_nodes": total_nodes - running_nodes,
        "wasted_monthly_spend": round(total_wasted, 2),
        "critical_security_risks": critical_security_risks,
        "last_synced": db["metadata"].get("timestamp")
    }

# --- 3. COMPUTE & STORAGE INVENTORY ---
@app.get("/api/v1/resources/nodes", response_model=List[NodeSchema])
async def get_nodes(status: Optional[str] = None, search: Optional[str] = None):
    return _frontend_nodes(status=status, search=search)

@app.get("/api/v1/resources/nodes/{instance_id}")
async def get_node_details(instance_id: str):
    _ensure_live_aws_state()
    nodes = mock_database.DB["nodes"]
    node = next((n for n in nodes if n["instance_id"] == instance_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Instance ID not found")
    details = _normalize_node(node)
    details["volumes_detail"] = [
        volume for volume in mock_database.DB.get("ebs_volumes", [])
        if any(attachment.get("InstanceId") == instance_id for attachment in volume.get("attachments", []))
        or volume.get("attached_instance_id") == instance_id
    ]
    details["network_interfaces"] = [
        eni for eni in mock_database.DB.get("network_interfaces", [])
        if eni.get("attached_instance_id") == instance_id
    ]
    return details


@app.get("/api/v1/resources/inventory")
async def get_full_inventory():
    """Return the complete live inventory collected by the notebook pipeline."""
    _ensure_live_aws_state()
    db = mock_database.DB
    return {
        "metadata": db["metadata"],
        "compute": {"nodes": db["nodes"]},
        "ec2_other_resources": {
            "ebs_volumes": db.get("ebs_volumes", []),
            "elastic_ips": db.get("elastic_ips", []),
            "amis": db.get("amis", []),
            "network_interfaces": db.get("network_interfaces", []),
            "ebs_snapshots": db.get("ebs_snapshots", []),
            "cloudwatch_log_groups": db.get("cloudwatch_log_groups", []),
            "s3_buckets": db.get("s3_buckets", []),
            "security_groups": db.get("security_groups", []),
        },
        "vpc_resources": db.get("vpc_resources", {"nat_gateways": [], "vpc_endpoints": []}),
    }


@app.get("/api/v1/connect-cloud/state")
async def get_connect_state():
    return _connection_state()


@app.post("/api/v1/connect-cloud/switch")
async def switch_connected_account(payload: dict):
    selector = {
        "provider": payload.get("provider"),
        "account_name": payload.get("account_name"),
        "region": payload.get("region"),
        "role_arn": payload.get("role_arn"),
        "access_key": payload.get("access_key") or payload.get("access_key_last4") or "",
    }
    match = _activate_connected_account(selector)
    if not _refresh_live_aws_state():
        connection = _connection_state()
        if _is_permission_denied(last_live_error):
            return {
                "status": "success",
                "message": "Switched AWS account with limited access",
                "warning": last_live_error,
                "access_mode": "limited",
                "connection": connection,
                "connected_accounts": connection.get("connected_accounts", []),
                "matched_account": _public_connection_record(match),
            }
        raise HTTPException(status_code=502, detail=f"AWS account switch succeeded, but live resource discovery failed: {last_live_error}")
    connection = _connection_state()
    return {
        "status": "success",
        "message": "Switched AWS account",
        "access_mode": "live",
        "connection": connection,
        "connected_accounts": connection.get("connected_accounts", []),
        "matched_account": _public_connection_record(match),
    }

# --- 4. TELEMETRY & METRIC ANALYTICS ---
@app.get("/api/v1/telemetry/{instance_id}")
async def get_instance_telemetry(instance_id: str):
    _ensure_live_aws_state()
    live = _live_instance_telemetry(instance_id)
    if live is not None:
        return {
            "instance_id": instance_id,
            "metrics": live,
        }
    return {
        "instance_id": instance_id,
        "metrics": [],
        "message": "CloudWatch metrics are unavailable or not permitted for this account.",
    }


# --- COMPATIBILITY ROUTES FOR THE NEXT.JS FRONTEND ---
@app.get("/api/nodes", response_model=List[NodeSchema])
async def get_frontend_nodes(status: Optional[str] = None, search: Optional[str] = None, provider: Optional[str] = None):
    return _frontend_nodes(status=status, search=search)


@app.get("/api/telemetry")
async def get_frontend_telemetry(timeframe: str = "24h", instance_id: Optional[str] = None):
    return _frontend_telemetry(timeframe=timeframe)


@app.get("/api/spend")
async def get_frontend_spend(provider: Optional[str] = None):
    return _frontend_spend()


@app.get("/api/alerts")
async def get_frontend_alerts():
    return _frontend_alerts()


@app.get("/api/optimizations")
async def get_frontend_optimizations():
    return _frontend_optimizations()


@app.get("/api/optimizations/applied")
async def get_frontend_applied_optimizations():
    _ensure_live_aws_state()
    return {"applied": _db().setdefault("applied_optimizations", [])}


@app.post("/api/security/revoke")
async def revoke_security_group(payload: dict):
    group_id = payload.get("groupId")
    db = _db()
    sg = next((item for item in db["security_groups"] if item["group_id"] == group_id), None)
    if not sg:
        raise HTTPException(status_code=404, detail="Security group not found")
    sg["is_publicly_exposed"] = False
    return {"status": "revoked", "groupId": group_id}


@app.post("/api/optimizations/apply")
async def apply_optimization(payload: dict):
    optimization_id = payload.get("id")
    action = payload.get("action", "apply")
    if not optimization_id:
        raise HTTPException(status_code=400, detail="Optimization id is required")
    applied = _db().setdefault("applied_optimizations", [])
    if action == "revert":
        if optimization_id in applied:
            applied.remove(optimization_id)
    elif optimization_id not in applied:
        applied.append(optimization_id)
    return {"status": "ok", "id": optimization_id, "action": action, "applied": applied}


@app.put("/api/settings")
async def update_settings(payload: dict):
    org_name = payload.get("orgName")
    if not org_name:
        raise HTTPException(status_code=400, detail="orgName is required")
    _db()["metadata"]["organization"] = org_name
    return {"status": "saved", "organization": org_name}


@app.get("/api/settings")
async def get_settings():
    metadata = _db()["metadata"]
    return {
        "organization": metadata.get("organization", ""),
        "region": metadata.get("region", "us-east-1"),
        "timestamp": metadata.get("timestamp"),
    }


@app.post("/api/accounts/connect")
async def connect_frontend_account(payload: dict):
    account_name = payload.get("accountName", "Connected account")
    cloud = payload.get("cloud", "AWS")
    role_arn = payload.get("roleArn")
    return {
        "status": "connected",
        "provider": cloud,
        "account_name": account_name,
        "role_arn": role_arn,
    }

# --- 5. SECURITY & EXPOSURE AUDIT ---
@app.get("/api/v1/security/audit")
async def get_security_audit():
    _ensure_live_aws_state()
    db = mock_database.DB
    return {
        "exposed_security_groups": [sg for sg in db["security_groups"] if sg["is_publicly_exposed"]],
        "unattached_elastic_ips": [eip for eip in db["elastic_ips"] if eip["is_unattached"]],
        "orphaned_ebs_volumes": [v for v in db["ebs_volumes"] if v.get("is_orphaned")]
    }

# --- 6. COST OPTIMIZATION RECOMMENDATIONS ---
@app.get("/api/v1/optimizations")
async def get_cost_optimizations():
    _ensure_live_aws_state()
    db = mock_database.DB
    recommendations = []

    # Check unattached EIPs
    for eip in db["elastic_ips"]:
        if eip["is_unattached"]:
            recommendations.append({
                "id": f"rec-eip-{eip['public_ip']}",
                "type": "Orphaned Resource",
                "title": f"Release Unattached Elastic IP ({eip['public_ip']})",
                "savings": eip["estimated_monthly_cost"],
                "effort": "Quick Win",
                "action": "release_eip"
            })

    # Check orphaned EBS volumes
    for vol in db["ebs_volumes"]:
        if vol.get("is_orphaned"):
            recommendations.append({
                "id": f"rec-vol-{vol['volume_id']}",
                "type": "Idle Storage",
                "title": f"Delete Unattached EBS Volume ({vol['volume_id']})",
                "savings": vol.get("cost", 8.00),
                "effort": "Low",
                "action": "delete_volume"
            })

    return {
        "total_potential_savings": sum(r["savings"] for r in recommendations),
        "recommendations": recommendations
    }

# --- 7. CONNECT CLOUD ACCOUNT ---
@app.post("/api/v1/connect-cloud", status_code=status.HTTP_200_OK)
async def connect_cloud_account(credentials: CloudConnectRequest):
    if credentials.provider.upper() == "AWS":
        if credentials.auth_method == "keys" and not (credentials.access_key and credentials.secret_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AWS key authentication requires Access Key ID and Secret Access Key."
            )
        # Validate AWS Learner Lab / Temporary Credentials
        if credentials.auth_method == "learner_lab":
            if not (credentials.access_key and credentials.secret_key and credentials.session_token):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AWS Learner Lab requires Access Key ID, Secret Access Key, AND Session Token."
                )

            try:
                # Test connection using Boto3 STS caller identity
                session = boto3.Session(
                    aws_access_key_id=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_session_token=credentials.session_token,
                    region_name=credentials.region
                )
                sts = session.client('sts', config=AWS_CLIENT_CONFIG)
                identity = sts.get_caller_identity()

                _save_active_credentials(credentials)
                if not _refresh_live_aws_state():
                    connection = _connection_state()
                    if _is_permission_denied(last_live_error):
                        _set_connection_mode("limited", last_live_error)
                        connection = _connection_state()
                        return {
                            "status": "success",
                            "provider": "AWS (Learner Lab)",
                            "account_id": identity.get("Account"),
                            "arn": identity.get("Arn"),
                            "message": "Connected with limited access",
                            "warning": last_live_error,
                            "access_mode": "limited",
                            "connection": connection,
                            "connected_accounts": connection.get("connected_accounts", []),
                        }
                    active_credentials.pop("default", None)
                    raise HTTPException(status_code=502, detail=f"AWS authentication succeeded, but live resource discovery failed: {last_live_error}")
                _set_connection_mode("live")
                connection = _connection_state()
                return {
                    "status": "success",
                    "provider": "AWS (Learner Lab)",
                    "account_id": identity.get("Account"),
                    "arn": identity.get("Arn"),
                    "message": "Success",
                    "access_mode": "live",
                    "connection": connection,
                    "connected_accounts": connection.get("connected_accounts", []),
                }
            except (ClientError, BotoCoreError) as e:
                message = e.response.get("Error", {}).get("Message", str(e)) if isinstance(e, ClientError) else str(e)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"AWS Authentication Failed: {message}"
                )

    _save_active_credentials(credentials)
    if credentials.provider.upper() == "AWS" and not _refresh_live_aws_state():
        connection = _connection_state()
        if _is_permission_denied(last_live_error):
            _set_connection_mode("limited", last_live_error)
            connection = _connection_state()
            return {
                "status": "success",
                "message": "Connected with limited access",
                "warning": last_live_error,
                "access_mode": "limited",
                "connection": connection,
                "connected_accounts": connection.get("connected_accounts", []),
            }
        active_credentials.pop("default", None)
        raise HTTPException(status_code=502, detail=f"AWS connection succeeded, but live resource discovery failed: {last_live_error}")
    _set_connection_mode("live")
    connection = _connection_state()
    return {
        "status": "success",
        "message": "Success",
        "access_mode": "live",
        "connection": connection,
        "connected_accounts": connection.get("connected_accounts", []),
    }
