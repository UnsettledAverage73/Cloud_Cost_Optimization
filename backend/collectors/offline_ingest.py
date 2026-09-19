"""
CloudPulse Offline Zero-Trust Ingestion Engine
Allows prospective enterprise clients to run full FinOps audits without granting live IAM access.
Parses AWS CLI JSON exports (describe-instances, describe-volumes, etc.) and CUR / FOCUS CSV files.
"""

import json
import csv
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("finops.collectors.offline_ingest")


class OfflineIngestionCollector:
    """
    Ingests offline AWS / multi-cloud metadata and billing files,
    standardizing them into the canonical CloudPulse inventory schema.
    """

    def __init__(self, data_path: Union[str, Path]):
        self.data_path = Path(data_path)

    def load_inventory(self) -> Dict[str, Any]:
        """
        Detects whether data_path is a directory of JSON files, a single JSON inventory,
        or a CUR/FOCUS CSV billing file, and parses it into standard inventory format.
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"Offline ingestion path does not exist: {self.data_path}")

        if self.data_path.is_file():
            suffix = self.data_path.suffix.lower()
            if suffix == ".json":
                return self._parse_json_file(self.data_path)
            elif suffix in [".csv", ".tsv"]:
                return self._parse_billing_csv(self.data_path)
            elif suffix == ".parquet":
                return self._parse_billing_parquet(self.data_path)
            else:
                raise ValueError(f"Unsupported file format: {suffix}. Expected .json, .csv, or .parquet")
        elif self.data_path.is_dir():
            parquet_files = list(self.data_path.glob("*.parquet"))
            if parquet_files:
                return self._parse_billing_parquet(self.data_path)
            return self._parse_directory(self.data_path)

        raise ValueError(f"Invalid path type for offline ingestion: {self.data_path}")

    def _parse_directory(self, dir_path: Path) -> Dict[str, Any]:
        """Parses a folder containing AWS CLI JSON output files."""
        nodes = []
        ebs_volumes = []
        elastic_ips = []
        security_groups = []
        cw_log_groups = []
        account_id = "offline-account"
        region = "us-east-1"

        # Check for unified inventory.json first
        for unified_name in ["inventory.json", "metadata_export.json", "cloudpulse_inventory.json"]:
            unified_file = dir_path / unified_name
            if unified_file.exists():
                return self._parse_json_file(unified_file)

        # Parse individual CLI dumps
        for p in dir_path.glob("*.json"):
            name = p.name.lower()
            try:
                data = json.loads(p.read_text())
            except Exception as e:
                logger.warning(f"Could not parse JSON file {p}: {e}")
                continue

            if "instance" in name or "ec2" in name:
                nodes.extend(self._extract_instances(data))
            elif "volume" in name or "ebs" in name:
                ebs_volumes.extend(self._extract_volumes(data))
            elif "address" in name or "eip" in name or "ip" in name:
                elastic_ips.extend(self._extract_eips(data))
            elif "security_group" in name or "sg" in name:
                security_groups.extend(self._extract_security_groups(data))
            elif "log" in name or "cloudwatch" in name:
                cw_log_groups.extend(self._extract_log_groups(data))

        # Calculate monthly costs
        compute_spend = sum(n.get("cost", 0.0) for n in nodes)
        storage_spend = sum(v.get("cost", 0.0) for v in ebs_volumes)
        network_spend = sum(3.60 for e in elastic_ips if e.get("is_unattached"))
        total_spend = round(compute_spend + storage_spend + network_spend, 2)

        return {
            "metadata": {
                "account_id": account_id,
                "region": region,
                "ingestion_mode": "offline_directory",
                "source_path": str(dir_path)
            },
            "compute": {"nodes": nodes},
            "ec2_other_resources": {
                "ebs_volumes": ebs_volumes,
                "elastic_ips": elastic_ips,
                "security_groups": security_groups,
                "cloudwatch_log_groups": cw_log_groups
            },
            "summary": {
                "estimated_monthly_spend": total_spend,
                "total_compute_nodes": len(nodes),
                "total_ebs_volumes": len(ebs_volumes),
                "total_elastic_ips": len(elastic_ips),
                "total_security_groups": len(security_groups)
            }
        }

    def _parse_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Parses a single JSON file."""
        data = json.loads(file_path.read_text())
        if isinstance(data, dict) and "compute" in data and "ec2_other_resources" in data:
            # Already canonical CloudPulse inventory
            data.setdefault("metadata", {})["ingestion_mode"] = "offline_file"
            return data

        # Check if it's AWS CLI describe-instances output
        if "Reservations" in data:
            nodes = self._extract_instances(data)
            spend = sum(n.get("cost", 0.0) for n in nodes)
            return {
                "metadata": {"account_id": "offline-account", "ingestion_mode": "offline_cli_json"},
                "compute": {"nodes": nodes},
                "ec2_other_resources": {"ebs_volumes": [], "elastic_ips": [], "security_groups": []},
                "summary": {"estimated_monthly_spend": spend, "total_compute_nodes": len(nodes)}
            }

        return data

    def _extract_instances(self, data: Any) -> List[Dict[str, Any]]:
        """Extracts EC2 instances from describe-instances dict or list."""
        instances = []
        raw_list = []

        if isinstance(data, dict):
            if "Reservations" in data:
                for res in data["Reservations"]:
                    raw_list.extend(res.get("Instances", []))
            elif "Instances" in data:
                raw_list.extend(data["Instances"])
            elif "nodes" in data:
                raw_list.extend(data["nodes"])
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            inst_id = item.get("InstanceId") or item.get("instance_id") or "i-unknown"
            inst_type = item.get("InstanceType") or item.get("instance_type") or "t3.micro"
            state = item.get("State", {})
            state_name = state.get("Name") if isinstance(state, dict) else item.get("state", "running")

            # Extract Name tag
            name_tag = inst_id
            tags = item.get("Tags") or item.get("tags") or []
            if isinstance(tags, list):
                for t in tags:
                    if t.get("Key") == "Name":
                        name_tag = t.get("Value", inst_id)
            elif isinstance(tags, dict):
                name_tag = tags.get("Name", inst_id)

            # Standard hourly pricing estimate
            hourly_rates = {
                "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208,
                "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
                "t4g.micro": 0.0084, "t4g.small": 0.0168, "t4g.medium": 0.0336,
                "m5.large": 0.096, "m5.xlarge": 0.192, "c5.large": 0.085,
            }
            hourly = hourly_rates.get(inst_type, 0.0104)
            monthly_cost = round(hourly * 730, 2) if state_name == "running" else 0.0

            instances.append({
                "instance_id": inst_id,
                "name": name_tag,
                "instance_type": inst_type,
                "state": state_name,
                "cost": monthly_cost,
                "hourly_rate": hourly,
                "metrics": item.get("metrics", {"cpu_utilization_avg": 0.5, "cpu_utilization_max": 2.0}),
                "tags": tags
            })

        return instances

    def _extract_volumes(self, data: Any) -> List[Dict[str, Any]]:
        """Extracts EBS volumes from describe-volumes dict or list."""
        volumes = []
        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get("Volumes") or data.get("ebs_volumes", [])
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            vol_id = item.get("VolumeId") or item.get("volume_id") or "vol-unknown"
            vol_type = item.get("VolumeType") or item.get("volume_type") or "gp3"
            size_gb = item.get("Size") or item.get("size_gb") or 20
            attachments = item.get("Attachments") or item.get("attachments") or []
            status = item.get("State") or item.get("status") or "available"
            is_orphaned = len(attachments) == 0 or status == "available"

            # Cost per GB: gp2 = $0.10, gp3 = $0.08, io2 = $0.125
            rate = 0.10 if vol_type == "gp2" else 0.08
            cost = round(size_gb * rate, 2)

            volumes.append({
                "volume_id": vol_id,
                "volume_type": vol_type,
                "size_gb": size_gb,
                "status": status,
                "is_orphaned": is_orphaned,
                "cost": cost,
                "attachments": attachments
            })

        return volumes

    def _extract_eips(self, data: Any) -> List[Dict[str, Any]]:
        """Extracts Elastic IPs from describe-addresses dict or list."""
        eips = []
        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get("Addresses") or data.get("elastic_ips", [])
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            ip = item.get("PublicIp") or item.get("public_ip") or "1.2.3.4"
            assoc = item.get("AssociationId") or item.get("association_id")
            inst_id = item.get("InstanceId") or item.get("instance_id")
            is_unattached = not assoc and not inst_id

            eips.append({
                "public_ip": ip,
                "allocation_id": item.get("AllocationId", ""),
                "association_id": assoc,
                "is_unattached": is_unattached,
                "cost": 3.60 if is_unattached else 0.0
            })

        return eips

    def _extract_security_groups(self, data: Any) -> List[Dict[str, Any]]:
        """Extracts security groups."""
        sgs = []
        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get("SecurityGroups") or data.get("security_groups", [])
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            sg_id = item.get("GroupId") or item.get("group_id") or "sg-unknown"
            sg_name = item.get("GroupName") or item.get("group_name") or "default"
            rules = item.get("IpPermissions") or item.get("inbound_rules", [])

            is_publicly_exposed = False
            for r in rules:
                for ip_range in r.get("IpRanges", []):
                    if ip_range.get("CidrIp") == "0.0.0.0/0":
                        is_publicly_exposed = True
                        break

            sgs.append({
                "group_id": sg_id,
                "group_name": sg_name,
                "is_publicly_exposed": is_publicly_exposed,
                "inbound_rules": rules
            })

        return sgs

    def _extract_log_groups(self, data: Any) -> List[Dict[str, Any]]:
        """Extracts CloudWatch log groups."""
        logs = []
        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get("logGroups") or data.get("cloudwatch_log_groups", [])
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            name = item.get("logGroupName") or item.get("log_group_name") or "unknown-log"
            retention = item.get("retentionInDays") or item.get("retention_in_days")
            stored_bytes = item.get("storedBytes", 0)
            stored_gb = round(stored_bytes / (1024 ** 3), 2) if stored_bytes else item.get("stored_gb", 5.0)

            logs.append({
                "log_group_name": name,
                "retention_in_days": retention,
                "is_never_expire": retention is None,
                "stored_gb": stored_gb,
                "cost": round(stored_gb * 0.50, 2)
            })

        return logs

    def _parse_billing_csv(self, csv_path: Path) -> Dict[str, Any]:
        """Parses an AWS CUR / FOCUS 1.0 CSV file into standard inventory."""
        nodes = []
        volumes = []
        total_spend = 0.0

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cost = float(row.get("lineItem/UnblendedCost") or row.get("EffectiveCost") or row.get("cost") or 0.0)
                total_spend += cost
                res_id = row.get("lineItem/ResourceId") or row.get("ResourceId") or row.get("resource_id", "")
                prod_code = row.get("lineItem/ProductCode") or row.get("ServiceName") or row.get("service", "")
                inst_type = row.get("product/instanceType") or row.get("instance_type", "t3.micro")

                if "AmazonEC2" in prod_code or "ec2" in prod_code.lower():
                    if res_id.startswith("i-"):
                        nodes.append({
                            "instance_id": res_id,
                            "instance_type": inst_type,
                            "cost": round(cost, 2),
                            "state": "running",
                            "metrics": {"cpu_utilization_avg": 0.8}
                        })
                    elif res_id.startswith("vol-"):
                        volumes.append({
                            "volume_id": res_id,
                            "volume_type": "gp2",
                            "size_gb": 50,
                            "cost": round(cost, 2),
                            "is_orphaned": False
                        })

        return {
            "metadata": {
                "account_id": "cur-billing-import",
                "ingestion_mode": "offline_csv",
                "source_file": str(csv_path)
            },
            "compute": {"nodes": nodes},
            "ec2_other_resources": {
                "ebs_volumes": volumes,
                "elastic_ips": [],
                "security_groups": []
            },
            "summary": {
                "estimated_monthly_spend": round(total_spend, 2),
                "total_compute_nodes": len(nodes),
                "total_ebs_volumes": len(volumes)
            }
        }

    def _parse_billing_parquet(self, parquet_path: Path) -> Dict[str, Any]:
        """Parses AWS CUR 2.0 / FOCUS 1.0 Parquet file(s) into standard inventory using DuckDB."""
        try:
            import duckdb
        except ImportError:
            raise RuntimeError("DuckDB is required to parse Parquet billing files. Please install duckdb.")

        conn = duckdb.connect(":memory:")
        path_str = str(parquet_path / "*.parquet") if parquet_path.is_dir() else str(parquet_path)

        cols_info = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{path_str}') LIMIT 1").fetchall()
        col_names = [c[0] for c in cols_info]

        cost_col = next((c for c in ["EffectiveCost", "lineItem/UnblendedCost", "lineItem/NetUnblendedCost", "BilledCost", "cost"] if c in col_names), None)
        res_col = next((c for c in ["ResourceId", "ResourceID", "lineItem/ResourceId", "resource_id"] if c in col_names), None)
        prod_col = next((c for c in ["ServiceName", "lineItem/ProductCode", "ProductCode", "service"] if c in col_names), None)
        type_col = next((c for c in ["ResourceType", "product/instanceType", "instance_type"] if c in col_names), None)

        cost_expr = f'COALESCE(TRY_CAST("{cost_col}" AS DOUBLE), 0.0)' if cost_col else "0.0"
        res_expr = f'COALESCE("{res_col}", \'\')' if res_col else "''"
        prod_expr = f'COALESCE("{prod_col}", \'\')' if prod_col else "''"
        type_expr = f'COALESCE("{type_col}", \'t3.micro\')' if type_col else "'t3.micro'"

        query = f"""
            SELECT 
                {res_expr} as resource_id,
                {prod_expr} as product_code,
                {type_expr} as instance_type,
                SUM({cost_expr}) as total_cost
            FROM read_parquet('{path_str}')
            GROUP BY 1, 2, 3
        """
        rows = conn.execute(query).fetchall()

        nodes = []
        volumes = []
        total_spend = 0.0

        for r_id, p_code, i_type, c_val in rows:
            cost = float(c_val or 0.0)
            total_spend += cost
            p_lower = str(p_code).lower()
            str_rid = str(r_id)

            if "ec2" in p_lower or "compute" in p_lower or str_rid.startswith("i-"):
                if str_rid.startswith("i-") or not str_rid.startswith("vol-"):
                    nodes.append({
                        "instance_id": str_rid or f"i-cur-{len(nodes)+1}",
                        "instance_type": str(i_type) if i_type else "t3.micro",
                        "cost": round(cost, 2),
                        "state": "running",
                        "metrics": {"cpu_utilization_avg": 0.8}
                    })
            elif "ebs" in p_lower or "storage" in p_lower or str_rid.startswith("vol-"):
                volumes.append({
                    "volume_id": str_rid or f"vol-cur-{len(volumes)+1}",
                    "volume_type": "gp2",
                    "size_gb": 50,
                    "cost": round(cost, 2),
                    "is_orphaned": False
                })

        return {
            "metadata": {
                "account_id": "cur-parquet-import",
                "ingestion_mode": "offline_parquet",
                "source_file": str(parquet_path)
            },
            "compute": {"nodes": nodes},
            "ec2_other_resources": {
                "ebs_volumes": volumes,
                "elastic_ips": [],
                "security_groups": []
            },
            "summary": {
                "estimated_monthly_spend": round(total_spend, 2),
                "total_compute_nodes": len(nodes),
                "total_ebs_volumes": len(volumes)
            }
        }

