import logging
from typing import Any, Dict, List, Optional
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.network")

EIP_IDLE_MONTHLY_COST = 3.60
NAT_GATEWAY_MONTHLY_BASE_COST = 32.40
ALB_MONTHLY_BASE_COST = 22.50


class NetworkCollector(AWSBaseCollector):
    """
    Collects Elastic IPs, NAT Gateways, VPC Endpoints, Network Interfaces,
    Load Balancers, and Security Groups.
    """

    def collect(self) -> Dict[str, Any]:
        eips = self.collect_elastic_ips()
        nat_gateways = self.collect_nat_gateways()
        vpc_endpoints = self.collect_vpc_endpoints()
        enis = self.collect_network_interfaces()
        load_balancers = self.collect_load_balancers()
        security_groups = self.collect_security_groups()

        return {
            "elastic_ips": eips,
            "nat_gateways": nat_gateways,
            "vpc_endpoints": vpc_endpoints,
            "network_interfaces": enis,
            "load_balancers": load_balancers,
            "security_groups": security_groups,
            "unattached_eips_count": sum(1 for ip in eips if ip["is_unattached"]),
            "idle_nat_gateways_count": sum(1 for n in nat_gateways if n.get("is_idle", False)),
            "idle_load_balancers_count": sum(1 for lb in load_balancers if lb.get("is_idle", False)),
            "open_security_groups_count": sum(1 for sg in security_groups if sg["is_publicly_exposed"]),
        }

    def collect_elastic_ips(self) -> List[Dict[str, Any]]:
        raw_eips = self.call("ec2", "describe_addresses", default={"Addresses": []})
        eips_list = raw_eips.get("Addresses", []) if isinstance(raw_eips, dict) else []
        eips: List[Dict[str, Any]] = []

        for address in eips_list:
            pub_ip = address.get("PublicIp", "")
            inst_id = address.get("InstanceId")
            assoc_id = address.get("AssociationId")
            is_unattached = not (inst_id or assoc_id)

            eips.append({
                "public_ip": pub_ip,
                "allocation_id": address.get("AllocationId"),
                "instance_id": inst_id,
                "association_id": assoc_id,
                "network_interface_id": address.get("NetworkInterfaceId"),
                "is_unattached": is_unattached,
                "tags": self.parse_tags(address.get("Tags")),
                "estimated_monthly_cost": EIP_IDLE_MONTHLY_COST if is_unattached else 0.0,
            })

        return eips

    def collect_nat_gateways(self) -> List[Dict[str, Any]]:
        raw_nats = self.paginate("ec2", "describe_nat_gateways", "NatGateways")
        nat_gateways: List[Dict[str, Any]] = []

        for nat in raw_nats:
            if nat.get("State") in ["deleted", "deleting"]:
                continue

            nat_id = nat.get("NatGatewayId", "unknown")
            vpc_id = nat.get("VpcId")
            subnet_id = nat.get("SubnetId")
            state = nat.get("State", "available")
            create_time = nat.get("CreateTime")

            nat_gateways.append({
                "nat_gateway_id": nat_id,
                "vpc_id": vpc_id,
                "subnet_id": subnet_id,
                "state": state,
                "create_time": create_time.isoformat() if create_time else None,
                "is_idle": False,  # Evaluated by CloudWatch analytics
                "estimated_monthly_base_cost": NAT_GATEWAY_MONTHLY_BASE_COST,
                "tags": self.parse_tags(nat.get("Tags")),
            })

        return nat_gateways

    def collect_vpc_endpoints(self) -> List[Dict[str, Any]]:
        raw_endpoints = self.paginate("ec2", "describe_vpc_endpoints", "VpcEndpoints")
        endpoints: List[Dict[str, Any]] = []

        for ep in raw_endpoints:
            ep_id = ep.get("VpcEndpointId", "unknown")
            service = ep.get("ServiceName", "")
            ep_type = ep.get("VpcEndpointType", "Gateway")

            endpoints.append({
                "vpc_endpoint_id": ep_id,
                "vpc_id": ep.get("VpcId"),
                "service_name": service,
                "endpoint_type": ep_type,
                "state": ep.get("State", "available"),
                "tags": self.parse_tags(ep.get("Tags")),
                "is_s3_gateway": ("s3" in service.lower() and ep_type.lower() == "gateway"),
            })

        return endpoints

    def collect_network_interfaces(self) -> List[Dict[str, Any]]:
        raw_enis = self.paginate("ec2", "describe_network_interfaces", "NetworkInterfaces")
        enis: List[Dict[str, Any]] = []

        for eni in raw_enis:
            eni_id = eni.get("NetworkInterfaceId", "unknown")
            status = eni.get("Status", "in-use")
            attachment = eni.get("Attachment") or {}
            association = eni.get("Association") or {}

            enis.append({
                "network_interface_id": eni_id,
                "status": status,
                "is_orphaned": status == "available",
                "attached_instance_id": attachment.get("InstanceId"),
                "private_ip": eni.get("PrivateIpAddress"),
                "public_ip": association.get("PublicIp"),
                "vpc_id": eni.get("VpcId"),
                "tags": self.parse_tags(eni.get("TagSet")),
            })

        return enis

    def collect_load_balancers(self) -> List[Dict[str, Any]]:
        raw_lbs = self.paginate("elbv2", "describe_load_balancers", "LoadBalancers")
        load_balancers: List[Dict[str, Any]] = []

        for lb in raw_lbs:
            lb_arn = lb.get("LoadBalancerArn", "")
            lb_name = lb.get("LoadBalancerName", "unknown")
            lb_type = lb.get("Type", "application")
            state = lb.get("State", {}).get("Code", "active")
            vpc_id = lb.get("VpcId")

            # Check target health to evaluate idle status
            is_idle = self._check_lb_idle(lb_arn)

            load_balancers.append({
                "load_balancer_arn": lb_arn,
                "name": lb_name,
                "type": lb_type,
                "state": state,
                "vpc_id": vpc_id,
                "is_idle": is_idle,
                "estimated_monthly_cost": ALB_MONTHLY_BASE_COST,
            })

        return load_balancers

    def _check_lb_idle(self, lb_arn: str) -> bool:
        """Checks if a load balancer has 0 target groups or 0 healthy targets."""
        try:
            tg_resp = self.call(
                "elbv2",
                "describe_target_groups",
                {"LoadBalancerArn": lb_arn},
                default={"TargetGroups": []},
            )
            tgs = tg_resp.get("TargetGroups", [])
            if not tgs:
                return True

            for tg in tgs:
                tg_arn = tg.get("TargetGroupArn")
                if not tg_arn:
                    continue
                health_resp = self.call(
                    "elbv2",
                    "describe_target_health",
                    {"TargetGroupArn": tg_arn},
                    default={"TargetHealthDescriptions": []},
                )
                targets = health_resp.get("TargetHealthDescriptions", [])
                healthy_targets = sum(
                    1 for t in targets if t.get("TargetHealth", {}).get("State") == "healthy"
                )
                if healthy_targets > 0:
                    return False
            return True
        except Exception:
            return False

    def collect_security_groups(self) -> List[Dict[str, Any]]:
        raw_sgs = self.paginate("ec2", "describe_security_groups", "SecurityGroups")
        security_groups: List[Dict[str, Any]] = []

        for sg in raw_sgs:
            group_id = sg.get("GroupId", "unknown")
            group_name = sg.get("GroupName", group_id)
            exposed_ports: List[int] = []
            is_public = False

            for perm in sg.get("IpPermissions", []):
                pub_cidrs = any(r.get("CidrIp") == "0.0.0.0/0" for r in perm.get("IpRanges", []))
                pub_ipv6 = any(r.get("CidrIpv6") == "::/0" for r in perm.get("Ipv6Ranges", []))

                if pub_cidrs or pub_ipv6:
                    is_public = True
                    fp = perm.get("FromPort")
                    tp = perm.get("ToPort")
                    if isinstance(fp, int):
                        exposed_ports.append(fp)
                    if isinstance(tp, int) and tp != fp:
                        exposed_ports.append(tp)

            security_groups.append({
                "group_id": group_id,
                "group_name": group_name,
                "vpc_id": sg.get("VpcId"),
                "is_publicly_exposed": is_public,
                "exposed_ports": sorted(set(exposed_ports)),
                "tags": self.parse_tags(sg.get("Tags")),
            })

        return security_groups
