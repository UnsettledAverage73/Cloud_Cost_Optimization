import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.network")


class NetworkOptimizer:
    """
    Evaluates VPC networking, NAT Gateways, and Gateway Endpoints to eliminate
    unnecessary data processing charges.
    """

    @staticmethod
    def analyze(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        nat_gateways = inventory.get("nat_gateways", [])
        vpc_endpoints = inventory.get("vpc_endpoints", [])

        # Map VPC IDs that have S3 Gateway Endpoints configured
        vpcs_with_s3_endpoint = {
            ep.get("vpc_id")
            for ep in vpc_endpoints
            if ep.get("is_s3_gateway") or ("s3" in ep.get("service_name", "").lower() and ep.get("endpoint_type") == "Gateway")
        }

        for nat in nat_gateways:
            vpc_id = nat.get("vpc_id", "")
            nat_id = nat.get("nat_gateway_id", "unknown")

            # 1. Missing S3 Gateway Endpoint in VPC
            if vpc_id and vpc_id not in vpcs_with_s3_endpoint:
                recommendations.append({
                    "id": f"network-s3-endpoint-{vpc_id}",
                    "resource_id": vpc_id,
                    "resource_type": "VPC Endpoint",
                    "category": "Network Architecture",
                    "type": "VPC Gateway Endpoint",
                    "title": f"Provision Free S3 Gateway Endpoint in VPC ({vpc_id})",
                    "description": (
                        f"VPC has active NAT Gateway ({nat_id}) but no S3 Gateway Endpoint. Internal S3 traffic "
                        f"routes through the NAT Gateway billing $0.045/GB. Creating an S3 Gateway Endpoint is completely FREE."
                    ),
                    "monthly_savings": 25.00,  # Estimated typical S3 data processing savings
                    "savings": 25.00,
                    "effort": "Quick Win",
                    "action": "create_s3_endpoint",
                    "action_type": "create_s3_endpoint",
                    "severity": "HIGH",
                    "risk": "NONE",
                })

            # 2. Idle NAT Gateway
            if nat.get("is_idle"):
                recommendations.append({
                    "id": f"network-nat-idle-{nat_id}",
                    "resource_id": nat_id,
                    "resource_type": "NAT Gateway",
                    "category": "Network Waste",
                    "type": "Idle NAT Gateway",
                    "title": f"Decommission Idle NAT Gateway ({nat_id})",
                    "description": (
                        "NAT Gateway processed virtually 0 bytes over the past 7 days, "
                        "yet incurs $32.40/month in base hourly availability charges."
                    ),
                    "monthly_savings": 32.40,
                    "savings": 32.40,
                    "effort": "Medium",
                    "action": "delete_nat_gateway",
                    "action_type": "delete_nat_gateway",
                    "severity": "HIGH",
                    "risk": "LOW",
                })

        # 3. Idle / Orphaned Elastic Load Balancers (0 active targets)
        for lb in inventory.get("load_balancers", []):
            target_count = lb.get("target_count", lb.get("active_targets", None))
            is_idle = lb.get("is_idle", False) or (target_count == 0)
            if is_idle:
                lb_arn = lb.get("arn", lb.get("load_balancer_arn", "unknown"))
                lb_name = lb.get("name", lb.get("load_balancer_name", lb_arn.split("/")[-2] if "/" in lb_arn else "unknown"))
                lb_type = lb.get("type", "application").upper()
                recommendations.append({
                    "id": f"network-lb-idle-{lb_name}",
                    "resource_id": lb_name,
                    "resource_type": f"{lb_type} Load Balancer",
                    "category": "Network Waste",
                    "type": "Idle Load Balancer",
                    "title": f"Decommission 0-Target {lb_type} Load Balancer ({lb_name})",
                    "description": (
                        f"Load Balancer '{lb_name}' has 0 registered healthy targets yet incurs "
                        f"base availability charges of ~$22.50/month ($0.0225/hr + LCU base)."
                    ),
                    "monthly_savings": 22.50,
                    "savings": 22.50,
                    "effort": "Quick Win",
                    "action": "delete_load_balancer",
                    "action_type": "delete_load_balancer",
                    "severity": "HIGH",
                    "risk": "LOW",
                })

        # 4. Public IPv4 Address Charges on Private Workloads ($3.60/month per IPv4)
        for node in inventory.get("nodes", []):
            pub_ip = node.get("public_ip")
            name = (node.get("name") or "").lower()
            role = (node.get("role") or "").lower()
            # If instance is a worker, database, internal, backend, or private service with an unnecessary public IP
            is_internal = any(k in name or k in role for k in ["worker", "backend", "db", "database", "internal", "batch", "crawler", "cron"])
            if pub_ip and is_internal:
                node_id = node.get("instance_id", "unknown")
                recommendations.append({
                    "id": f"network-ipv4-private-{node_id}",
                    "resource_id": node_id,
                    "resource_type": "EC2 Public IPv4",
                    "category": "Network Architecture",
                    "type": "Unnecessary Public IPv4",
                    "title": f"Disassociate Public IPv4 ({pub_ip}) on Internal Worker {node.get('name', node_id)}",
                    "description": (
                        f"AWS charges $0.005/hr ($3.60/mo) for every public IPv4 address. Internal worker "
                        f"'{node.get('name', node_id)}' does not serve public traffic and should use private VPC routing."
                    ),
                    "monthly_savings": 3.60,
                    "savings": 3.60,
                    "effort": "Quick Win",
                    "action": "disassociate_public_ip",
                    "action_type": "disassociate_public_ip",
                    "severity": "MEDIUM",
                    "risk": "NONE",
                })

        return sorted(recommendations, key=lambda r: r["monthly_savings"], reverse=True)
