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
        cls, resource_id: str, tags: Dict[str, str], action: str
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
                if action in ["delete_volume", "stop_instance", "delete_snapshot"]:
                    return False, f"Resource '{resource_id}' is in PRODUCTION environment. Automated destruction is blocked."

        return True, "Guardrail checks passed."
