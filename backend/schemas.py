from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

# --- INGESTION & RESOURCE SCHEMAS ---
class NodeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    instance_id: str
    name: Optional[str] = "unnamed-node"
    type: str = Field(..., alias="instance_type")
    state: str
    platform: Optional[str] = "linux"
    availability_zone: Optional[str] = "us-east-1a"
    region: Optional[str] = "us-east-1"
    public_ip: Optional[str] = None
    volumes: int = 0
    cost: float = 12.40

class EBSVolumeSchema(BaseModel):
    volume_id: str
    size_gb: int
    volume_type: str
    iops: Optional[int] = 3000
    status: str
    is_orphaned: bool = False
    cost: float = 8.00

class ElasticIPSchema(BaseModel):
    public_ip: str
    is_unattached: bool
    estimated_monthly_cost: float = 3.60

class SecurityGroupSchema(BaseModel):
    group_id: str
    group_name: str
    is_publicly_exposed: bool
    exposed_ports: List[int]

class TelemetryPointSchema(BaseModel):
    timestamp: str
    cpu_utilization: float
    mem_used_percent: float
    net_in_mb: Optional[float] = 120.5
    net_out_mb: Optional[float] = 340.2

# --- FULL INGESTION PAYLOAD SCHEMA ---
class IngestionPayload(BaseModel):
    metadata: dict
    compute: dict
    ec2_other_resources: dict
    telemetry: List[TelemetryPointSchema]

# --- CONNECT CLOUD CREDENTIALS SCHEMA ---
class CloudConnectRequest(BaseModel):
    provider: str  # "AWS", "GCP", or "Azure"
    account_name: str
    auth_method: str = "keys"  # "keys", "learner_lab", or "iam_role"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    session_token: Optional[str] = None  # Added for AWS Learner Lab / STS
    role_arn: Optional[str] = None
    region: str = "us-east-1"
