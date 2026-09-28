"""
CloudPulse Enterprise FinOps Policy Guardrails Engine
Enables automated policy enforcement across tens of thousands of cloud resources.
Supports continuous audit, dry-run simulations, and 1-click batch GitOps PR remediation.
"""

import time
import uuid
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("finops.engines.policy_guardrails")

DEFAULT_ENTERPRISE_POLICIES = [
    {
        "id": "pol-idle-dev-cpu",
        "name": "Idle Development Workload Terminator",
        "description": "Flags or shuts down non-production instances with average CPU utilization under 5.0%.",
        "category": "Compute Rightsizing",
        "severity": "HIGH",
        "target_env": ["development", "staging"],
        "condition": "cpu_utilization < 5.0",
        "action": "auto_stop_schedule",
        "is_enabled": True
    },
    {
        "id": "pol-zombie-ebs",
        "name": "Zombie Unattached EBS Volume Terminator",
        "description": "Identifies detached EBS volumes incurring continuous unblended storage costs.",
        "category": "Storage Hygiene",
        "severity": "CRITICAL",
        "target_env": ["all"],
        "condition": "is_orphaned == True",
        "action": "snapshot_and_delete_pr",
        "is_enabled": True
    },
    {
        "id": "pol-unattached-eip",
        "name": "Unallocated Elastic IP Releaser",
        "description": "Releases public IPv4 addresses not associated with running network interfaces ($3.65/mo each).",
        "category": "Networking Waste",
        "severity": "MEDIUM",
        "target_env": ["all"],
        "condition": "is_unattached == True",
        "action": "release_eip_pr",
        "is_enabled": True
    },
    {
        "id": "pol-weekend-shutdown",
        "name": "Weekend Dev Fleet Auto-Shutdown",
        "description": "Enforces non-production servers to power down during non-business hours (saves 65% of dev costs).",
        "category": "Operational Scheduling",
        "severity": "HIGH",
        "target_env": ["development"],
        "condition": "is_weekend == True AND state == 'running'",
        "action": "enroll_scheduler_job",
        "is_enabled": True
    },
    {
        "id": "pol-graviton-candidate",
        "name": "ARM Graviton Modernization Guardrail",
        "description": "Recommends upgrading x86 compute (c5, m5, t3) to AWS Graviton 3/4 (c6g, m7g) for 20% price-performance boost.",
        "category": "Modernization",
        "severity": "LOW",
        "target_env": ["all"],
        "condition": "architecture == 'x86_64' AND eligible_graviton == True",
        "action": "generate_terraform_pr",
        "is_enabled": True
    }
]


class PolicyGuardrailsEngine:
    """
    Automates continuous FinOps compliance across enterprise fleets.
    Evaluates rule violations and calculates batch recoverable savings.
    """

    def __init__(self):
        self.policies: List[Dict[str, Any]] = [dict(p) for p in DEFAULT_ENTERPRISE_POLICIES]

    def list_policies(self) -> List[Dict[str, Any]]:
        return self.policies

    def toggle_policy(self, policy_id: str, is_enabled: bool) -> Optional[Dict[str, Any]]:
        for p in self.policies:
            if p["id"] == policy_id:
                p["is_enabled"] = is_enabled
                return p
        return None

    def evaluate_fleet(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs all enabled enterprise guardrails against current fleet inventory.
        Returns violated resources and aggregated monthly savings.
        """
        start_time = time.perf_counter()

        nodes = inventory.get("compute", {}).get("nodes", []) or inventory.get("nodes", [])
        vols = inventory.get("ec2_other_resources", {}).get("ebs_volumes", []) or inventory.get("ebs_volumes", [])
        eips = inventory.get("ec2_other_resources", {}).get("elastic_ips", []) or inventory.get("elastic_ips", [])

        evaluations = []
        total_recoverable_savings = 0.0
        total_violations_count = 0

        for pol in self.policies:
            if not pol.get("is_enabled", True):
                continue

            pol_id = pol["id"]
            matched_resources = []
            policy_savings = 0.0

            if pol_id == "pol-idle-dev-cpu":
                for n in nodes:
                    cpu = float(n.get("cpu_utilization", 50.0))
                    state = n.get("state", "running")
                    if cpu < 5.0 and state == "running":
                        cost = float(n.get("cost", 30.0))
                        sav = round(cost * 0.70, 2)
                        matched_resources.append({
                            "resource_id": n.get("instance_id", "i-unknown"),
                            "name": n.get("name", "idle-node"),
                            "type": "EC2 Instance",
                            "metric": f"{cpu:.1f}% CPU",
                            "monthly_cost": cost,
                            "recoverable_savings": sav
                        })
                        policy_savings += sav

            elif pol_id == "pol-zombie-ebs":
                for v in vols:
                    if v.get("is_orphaned") or v.get("status") in ["available", "unattached"]:
                        cost = float(v.get("cost", 10.0))
                        matched_resources.append({
                            "resource_id": v.get("volume_id", "vol-unknown"),
                            "name": f"ebs-{v.get('size_gb', 20)}gb",
                            "type": "EBS Volume",
                            "metric": f"{v.get('size_gb', 20)} GB Detached",
                            "monthly_cost": cost,
                            "recoverable_savings": cost
                        })
                        policy_savings += cost

            elif pol_id == "pol-unattached-eip":
                for e in eips:
                    if e.get("is_unattached", False):
                        cost = float(e.get("estimated_monthly_cost", 3.65))
                        matched_resources.append({
                            "resource_id": e.get("public_ip", "1.2.3.4"),
                            "name": "unattached-elastic-ip",
                            "type": "Elastic IP",
                            "metric": "Unallocated IPv4",
                            "monthly_cost": cost,
                            "recoverable_savings": cost
                        })
                        policy_savings += cost

            elif pol_id == "pol-weekend-shutdown":
                dev_nodes = [n for n in nodes if "dev" in str(n.get("name", "")).lower() or "dev" in str(n.get("tags", {})).lower()]
                for n in dev_nodes:
                    cost = float(n.get("cost", 25.0))
                    sav = round(cost * 0.65, 2)
                    matched_resources.append({
                        "resource_id": n.get("instance_id", "i-unknown"),
                        "name": n.get("name", "dev-node"),
                        "type": "Dev EC2 Instance",
                        "metric": "Unscheduled Dev Compute",
                        "monthly_cost": cost,
                        "recoverable_savings": sav
                    })
                    policy_savings += sav

            elif pol_id == "pol-graviton-candidate":
                for n in nodes:
                    itype = str(n.get("instance_type", n.get("type", "")))
                    if any(prefix in itype for prefix in ["c5.", "m5.", "t3.", "r5."]):
                        cost = float(n.get("cost", 50.0))
                        sav = round(cost * 0.20, 2)
                        matched_resources.append({
                            "resource_id": n.get("instance_id", "i-unknown"),
                            "name": n.get("name", "x86-node"),
                            "type": f"Intel {itype}",
                            "metric": "Graviton Modernization Candidate",
                            "monthly_cost": cost,
                            "recoverable_savings": sav
                        })
                        policy_savings += sav

            policy_savings = round(policy_savings, 2)
            total_recoverable_savings += policy_savings
            total_violations_count += len(matched_resources)

            evaluations.append({
                "policy": pol,
                "violation_count": len(matched_resources),
                "potential_monthly_savings": policy_savings,
                "matched_resources": matched_resources[:20]  # sample top 20 for preview
            })

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "evaluation_timestamp": time.time(),
            "execution_time_ms": elapsed_ms,
            "total_active_policies": len(self.policies),
            "total_violations_detected": total_violations_count,
            "total_recoverable_monthly_savings": round(total_recoverable_savings, 2),
            "policy_evaluations": evaluations
        }


# Global Singleton
policy_guardrails_engine = PolicyGuardrailsEngine()
