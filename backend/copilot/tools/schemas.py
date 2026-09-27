"""
CloudPulse Copilot Tool Schemas & Function-Calling Specifications.
Defines typed Pydantic models and standard JSON tool definitions for the
One-Model Autonomous AI System Architect.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# 1. PYDANTIC TOOL INPUT VALIDATION SCHEMAS
# =============================================================================

class PricingLookupInput(BaseModel):
    resource_type: str = Field(
        ...,
        description="The AWS instance type (e.g., 'm5.2xlarge', 't4g.medium') or storage class (e.g., 'gp3', 'io1')."
    )
    region: str = Field(
        default="us-east-1",
        description="The AWS region to look up pricing for (default: 'us-east-1')."
    )


class CloudTrailForensicsInput(BaseModel):
    service: str = Field(
        default="AmazonEC2",
        description="The AWS service name to investigate for cost spike events (e.g., 'AmazonEC2', 'AmazonRDS', 'AmazonS3')."
    )
    hours_back: int = Field(
        default=168,
        description="The number of hours back to investigate (default: 168 hours / 7 days)."
    )
    allow_simulation: bool = Field(
        default=True,
        description="Whether to return a high-fidelity synthetic demo event if live CloudTrail returns no records."
    )


class SQLAnalyticsInput(BaseModel):
    query: str = Field(
        ...,
        description="Read-only SELECT SQL query to execute against the TimescaleDB billing and telemetry tables."
    )


class TerraformPRInput(BaseModel):
    finding_id: str = Field(..., description="Unique identifier for the optimization finding.")
    resource_id: str = Field(..., description="AWS Resource ID (e.g., 'i-036358db85d245e3a').")
    action_type: str = Field(
        default="downsize_ec2",
        description="Remediation action (e.g., 'downsize_ec2', 'upgrade_gp3', 'delete_unattached_ebs')."
    )
    current_config: Dict[str, Any] = Field(default_factory=dict, description="Current resource configuration.")
    recommended_config: Dict[str, Any] = Field(default_factory=dict, description="Target optimized configuration.")
    monthly_savings: float = Field(default=50.0, description="Estimated monthly dollar savings.")


class KubernetesAllocationsInput(BaseModel):
    namespace: Optional[str] = Field(None, description="Optional Kubernetes namespace to filter workload efficiency.")
    cluster_id: Optional[str] = Field(None, description="Optional cluster identifier.")


class FOCUSLakehouseInput(BaseModel):
    query_type: str = Field(
        default="spend_by_service",
        description="Query type: 'spend_by_service' or 'top_drivers'."
    )
    limit: int = Field(default=5, description="Number of results to return.")


class VectorKnowledgeInput(BaseModel):
    query: str = Field(..., description="Semantic search query for FinOps policies or architecture guides.")
    limit: int = Field(default=3, description="Number of policy documents to retrieve.")


# =============================================================================
# 2. FUNCTION-CALLING TOOL DEFINITIONS FOR LLM
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "pricing_rag",
            "description": "Look up AWS compute or storage pricing, hourly/monthly on-demand rates, Spot, Savings Plans, and Graviton migration recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "description": "The AWS instance type (e.g. 'm5.2xlarge', 't3.medium') or storage type ('gp2', 'gp3')."
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region code, defaults to 'us-east-1'."
                    }
                },
                "required": ["resource_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cloudtrail_forensics",
            "description": "Investigate root cause of cloud spend surges by querying CloudTrail events (who launched or modified resources).",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "AWS service to investigate (AmazonEC2, AmazonRDS, AmazonS3)."
                    },
                    "allow_simulation": {
                        "type": "boolean",
                        "description": "Allow demo synthetic event fallback if no live events exist."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sql_analytics",
            "description": "Execute a safe, read-only SELECT query against the TimescaleDB FinOps ledger (tables: daily_spend_records, resource_telemetry, cloud_resources, optimization_findings).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SELECT query to execute."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terraform_pr",
            "description": "Generate an automated Terraform / OpenTofu pull request diff and migration plan for a cost optimization finding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "finding_id": {"type": "string", "description": "Finding identifier."},
                    "resource_id": {"type": "string", "description": "Target AWS resource ID."},
                    "action_type": {"type": "string", "description": "Action (e.g. 'downsize_ec2', 'upgrade_gp3')."},
                    "current_config": {"type": "object", "description": "Current resource attributes."},
                    "recommended_config": {"type": "object", "description": "Target optimized attributes."},
                    "monthly_savings": {"type": "number", "description": "Estimated monthly savings in USD."}
                },
                "required": ["finding_id", "resource_id", "action_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kubernetes_allocations",
            "description": "Query Kubernetes container allocations, CPU/memory efficiency, and OpenCost rightsizing recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Kubernetes namespace filter."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "focus_lakehouse",
            "description": "Query the FOCUS 1.0 multi-cloud analytical lakehouse for spend breakdown by service or top cost drivers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["spend_by_service", "top_drivers"],
                        "description": "Type of query to run."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vector_knowledge",
            "description": "Semantic search over indexed FinOps organizational policies, AWS Well-Architected frameworks, and optimization playbooks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Semantic search query."},
                    "limit": {"type": "integer", "description": "Max documents to retrieve."}
                },
                "required": ["query"]
            }
        }
    }
]
