import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.s3")

S3_STANDARD_PER_GB = 0.023
S3_INTELLIGENT_TIERING_PER_GB = 0.0125
S3_GLACIER_PER_GB = 0.004


class S3Collector(AWSBaseCollector):
    """
    Collects S3 Buckets, lifecycle transition rules, multipart upload expiration,
    and storage tiering opportunities.
    """

    def collect(self) -> Dict[str, Any]:
        buckets = self.collect_buckets()
        missing_lifecycle = sum(1 for b in buckets if not b["has_lifecycle_policy"])
        missing_multipart = sum(1 for b in buckets if not b["aborts_incomplete_multipart"])
        return {
            "buckets": buckets,
            "total_buckets": len(buckets),
            "missing_lifecycle_count": missing_lifecycle,
            "missing_multipart_cleanup_count": missing_multipart,
        }

    def collect_buckets(self) -> List[Dict[str, Any]]:
        raw_buckets = self.call("s3", "list_buckets", default={"Buckets": []})
        buckets_list = raw_buckets.get("Buckets", []) if isinstance(raw_buckets, dict) else []
        buckets: List[Dict[str, Any]] = []

        for b in buckets_list:
            name = b.get("Name")
            if not name:
                continue

            creation_date = b.get("CreationDate")

            # Check Lifecycle rules
            lifecycle = self.call(
                "s3",
                "get_bucket_lifecycle_configuration",
                {"Bucket": name},
                default=None,
            )

            has_lifecycle = False
            has_transitions = False
            has_incomplete_multipart_rule = False
            transition_targets = []

            if lifecycle and isinstance(lifecycle, dict) and "Rules" in lifecycle:
                has_lifecycle = True
                for rule in lifecycle.get("Rules", []):
                    if rule.get("Status") == "Enabled":
                        if rule.get("Transitions"):
                            has_transitions = True
                            for t in rule["Transitions"]:
                                if t.get("StorageClass"):
                                    transition_targets.append(t["StorageClass"])
                        if rule.get("AbortIncompleteMultipartUpload"):
                            has_incomplete_multipart_rule = True

            # Check Bucket Location
            loc_resp = self.call("s3", "get_bucket_location", {"Bucket": name}, default={})
            bucket_region = loc_resp.get("LocationConstraint") or "us-east-1"
            if bucket_region == "EU":
                bucket_region = "eu-west-1"

            # Check Bucket Tagging
            tag_resp = self.call("s3", "get_bucket_tagging", {"Bucket": name}, default={})
            tags = self.parse_tags(tag_resp.get("TagSet", []))

            # Query CloudWatch for actual storage size if available
            stored_bytes = self._get_bucket_size_bytes(name, bucket_region)
            stored_gb = round(stored_bytes / (1024 ** 3), 2)
            estimated_monthly_cost = round(stored_gb * S3_STANDARD_PER_GB, 2)

            buckets.append({
                "bucket_name": name,
                "region": bucket_region,
                "creation_date": creation_date.isoformat() if creation_date else None,
                "has_lifecycle_policy": has_lifecycle,
                "has_transitions": has_transitions,
                "transition_targets": list(set(transition_targets)),
                "aborts_incomplete_multipart": has_incomplete_multipart_rule,
                "stored_bytes": stored_bytes,
                "stored_gb": stored_gb,
                "estimated_monthly_cost": estimated_monthly_cost,
                "tags": tags,
            })

        return buckets

    def _get_bucket_size_bytes(self, bucket_name: str, bucket_region: str) -> int:
        """
        Attempts to fetch CloudWatch BucketSizeBytes for standard storage.
        """
        try:
            cw = self.get_client("cloudwatch", custom_region=bucket_region)
            end_time = datetime.now(timezone.utc)
            from datetime import timedelta
            start_time = end_time - timedelta(days=2)

            resp = cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "StandardStorage"},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average"],
            )
            datapoints = resp.get("Datapoints", [])
            if datapoints:
                latest = max(datapoints, key=lambda p: p["Timestamp"])
                return int(latest.get("Average", 0))
        except Exception:
            pass
        return 0
