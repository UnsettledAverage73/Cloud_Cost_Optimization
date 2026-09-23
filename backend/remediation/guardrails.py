import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger("finops.remediation.guardrails")

PROTECTED_TAG_KEYS = {"keepalive", "donotdelete", "do_not_delete", "protected"}
PRODUCTION_VALUES = {"prod", "production", "live"}


class RemediationGuardrails:
    """
    Guarantees safety guardrails before executing any cloud resource remediation.
    """

    @classmethod
    def check_safe_to_remediate(
        cls, resource_id: str, tags: Dict[str, str], action: str, allow_production_override: bool = False
    ) -> Tuple[bool, str]:
        """
        Validates if resource is protected by tag policies or production environments.
        """
        # 1. Check protection tags
        for key, value in tags.items():
            lower_k = key.lower().strip()
            lower_v = str(value).lower().strip()

            if lower_k in PROTECTED_TAG_KEYS and lower_v in ["true", "yes", "1"]:
                return False, f"Resource '{resource_id}' is protected by safety tag '{key}={value}'."

            if lower_k in ["environment", "env"] and lower_v in PRODUCTION_VALUES:
                # Disallow destructive actions in production without override
                if action in ["delete_volume", "stop_instance", "stop", "delete_snapshot"] and not allow_production_override:
                    return False, f"Resource '{resource_id}' is in PRODUCTION environment. Automated destruction is blocked (use --force to override)."

            # 2. Check Auto Scaling Group membership
            if lower_k in ["aws:autoscaling:groupname", "asg_name"] and not allow_production_override:
                if action in ["stop_instance", "downsize", "resize", "stop"]:
                    return False, (
                        f"Resource '{resource_id}' belongs to Auto Scaling Group '{value}'. "
                        f"Direct instance modification is blocked to prevent ASG node recycling. "
                        f"Update the ASG Launch Template or use --force to override."
                    )

            # 3. Check memory headroom safety
            if lower_k in ["mem_max", "memory_max_percent"] and not allow_production_override:
                try:
                    if float(value) > 65.0 and action in ["downsize", "resize", "modify_instance_type"]:
                        return False, (
                            f"Resource '{resource_id}' has high memory consumption ({value}%). "
                            f"Downsizing is BLOCKED by memory guardrail to prevent Out-Of-Memory (OOM) crashes (use --force to override)."
                        )
                except ValueError:
                    pass

        return True, "Guardrail checks passed."
