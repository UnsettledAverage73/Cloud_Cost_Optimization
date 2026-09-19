import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.storage")


class StorageOptimizer:
    """
    Evaluates EBS volume modernization (gp2 -> gp3) and S3 bucket lifecycle optimizations.
    """

    @staticmethod
    def analyze(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        # 1. EBS gp2 -> gp3 Modernization
        for vol in inventory.get("ebs_volumes", []):
            vol_type = str(vol.get("volume_type", "gp3")).lower()
            if vol_type == "gp2" and not vol.get("is_orphaned"):
                vol_id = vol.get("volume_id", "unknown")
                size_gb = vol.get("size_gb", 0)
                # gp2 is $0.10/GB, gp3 is $0.08/GB -> $0.02/GB savings (20%)
                monthly_savings = round(size_gb * 0.02, 2)
                attached_inst = vol.get("attached_instance_id", "detached")

                recommendations.append({
                    "id": f"storage-gp3-{vol_id}",
                    "resource_id": vol_id,
                    "resource_type": "EBS Volume",
                    "category": "Storage Modernization",
                    "type": "Volume Upgrade",
                    "title": f"Upgrade Volume {vol_id} ({size_gb} GB) from gp2 to gp3",
                    "description": (
                        f"Migrating to gp3 saves 20% ($0.02/GB/mo) while boosting baseline "
                        f"performance to 3,000 IOPS and 125 MB/s without instance downtime."
                    ),
                    "monthly_savings": max(0.50, monthly_savings),
                    "savings": max(0.50, monthly_savings),
                    "effort": "Quick Win",
                    "action": "upgrade_gp3",
                    "action_type": "upgrade_gp3",
                    "severity": "MEDIUM",
                    "risk": "NONE",
                })

        # 2. S3 Buckets Missing Lifecycle Transitions
        for bucket in inventory.get("s3_buckets", []):
            b_name = bucket.get("bucket_name", "unknown")
            has_lifecycle = bucket.get("has_lifecycle_policy", False)
            stored_gb = bucket.get("stored_gb", 0.0)

            if not has_lifecycle:
                # Intelligent-Tiering or Standard-IA saves ~45%
                potential_savings = round(stored_gb * 0.023 * 0.45, 2) if stored_gb > 0 else 5.0
                recommendations.append({
                    "id": f"storage-s3-lifecycle-{b_name}",
                    "resource_id": b_name,
                    "resource_type": "S3 Bucket",
                    "category": "Storage Tiering",
                    "type": "Lifecycle Policy",
                    "title": f"Enable S3 Intelligent-Tiering Lifecycle on '{b_name}'",
                    "description": (
                        f"Bucket has no lifecycle transition rules. Enabling Intelligent-Tiering "
                        f"automatically moves objects accessed rarely to cheaper tiers, saving up to 45%."
                    ),
                    "monthly_savings": max(2.50, potential_savings),
                    "savings": max(2.50, potential_savings),
                    "effort": "Low",
                    "action": "configure_s3_lifecycle",
                    "action_type": "configure_s3_lifecycle",
                    "severity": "LOW",
                    "risk": "NONE",
                })

            # Incomplete multipart upload cleanup
            if not bucket.get("aborts_incomplete_multipart", False):
                recommendations.append({
                    "id": f"storage-s3-multipart-{b_name}",
                    "resource_id": b_name,
                    "resource_type": "S3 Bucket",
                    "category": "Storage Waste",
                    "type": "Multipart Upload Cleanup",
                    "title": f"Configure 7-Day Incomplete Multipart Cleanup on '{b_name}'",
                    "description": (
                        "Failed or interrupted multi-part file uploads accumulate non-visible storage "
                        "bytes billed at standard S3 rates. Add rule to abort after 7 days."
                    ),
                    "monthly_savings": 2.00,
                    "savings": 2.00,
                    "effort": "Quick Win",
                    "action": "configure_multipart_cleanup",
                    "action_type": "configure_multipart_cleanup",
                    "severity": "LOW",
                    "risk": "NONE",
                })

        # 3. High-Cost io1 / io2 Volumes Migratable to gp3
        for vol in inventory.get("ebs_volumes", []):
            vol_type = str(vol.get("volume_type", "")).lower()
            if vol_type in ["io1", "io2"]:
                vol_id = vol.get("volume_id", "unknown")
                size_gb = vol.get("size_gb", 0)
                iops = vol.get("iops", 3000)
                # io1 is $0.125/GB + $0.065/IOPS; gp3 is $0.08/GB with 3000 IOPS included
                current_cost = (size_gb * 0.125) + (iops * 0.065)
                gp3_cost = (size_gb * 0.08) + (max(0, iops - 3000) * 0.005)
                monthly_savings = max(15.0, round(current_cost - gp3_cost, 2))

                recommendations.append({
                    "id": f"storage-io-to-gp3-{vol_id}",
                    "resource_id": vol_id,
                    "resource_type": "EBS Volume",
                    "category": "Storage Modernization",
                    "type": "High-Cost Volume Downgrade",
                    "title": f"Modernize Expensive {vol_type.upper()} Volume {vol_id} to gp3",
                    "description": (
                        f"Volume {vol_id} uses costly {vol_type.upper()} storage ($0.125/GB + IOPS fee). "
                        f"Modernizing to gp3 delivers identical baseline 3,000 IOPS while reducing monthly cost by over 50%."
                    ),
                    "monthly_savings": monthly_savings,
                    "savings": monthly_savings,
                    "effort": "Quick Win",
                    "action": "upgrade_gp3",
                    "action_type": "upgrade_gp3",
                    "severity": "HIGH",
                    "risk": "LOW",
                })

        # 4. Stale EBS Snapshots (> 90 Days Old)
        for snap in inventory.get("ebs_snapshots", []):
            age_days = snap.get("age_days", 0)
            is_stale = snap.get("is_stale", False) or age_days > 90
            if is_stale:
                snap_id = snap.get("snapshot_id", "unknown")
                size_gb = snap.get("size_gb", 20)
                monthly_savings = max(1.0, round(size_gb * 0.05, 2))
                recommendations.append({
                    "id": f"storage-snapshot-stale-{snap_id}",
                    "resource_id": snap_id,
                    "resource_type": "EBS Snapshot",
                    "category": "Storage Waste",
                    "type": "Stale Snapshot",
                    "title": f"Prune Stale {age_days}-Day Old Snapshot ({snap_id})",
                    "description": (
                        f"Snapshot {snap_id} ({size_gb} GB) is {age_days} days old with no automated lifecycle rule. "
                        f"Deleting obsolete incremental snapshots eliminates recurring storage charges."
                    ),
                    "monthly_savings": monthly_savings,
                    "savings": monthly_savings,
                    "effort": "Quick Win",
                    "action": "delete_snapshot",
                    "action_type": "delete_snapshot",
                    "severity": "LOW",
                    "risk": "NONE",
                })

        return sorted(recommendations, key=lambda r: r["monthly_savings"], reverse=True)
