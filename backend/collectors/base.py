import logging
import time
from typing import Any, Callable, Dict, List, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("finops.collectors")

DEFAULT_AWS_CONFIG = Config(
    connect_timeout=4,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)


class AWSBaseCollector:
    """
    Base collector providing resilient AWS client creation, paginated API execution,
    graceful permission degradation, and throttling back-off.
    """

    def __init__(self, session: boto3.Session, region: Optional[str] = None):
        self.session = session
        self.region = region or session.region_name or "us-east-1"
        self._clients: Dict[str, Any] = {}

    def get_client(self, service_name: str, custom_region: Optional[str] = None) -> Any:
        reg = custom_region or self.region
        cache_key = f"{service_name}:{reg}"
        if cache_key not in self._clients:
            self._clients[cache_key] = self.session.client(
                service_name,
                region_name=reg,
                config=DEFAULT_AWS_CONFIG,
            )
        return self._clients[cache_key]

    def paginate(
        self,
        service_name: str,
        operation_name: str,
        result_key: str,
        paginate_kwargs: Optional[Dict[str, Any]] = None,
        custom_region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes an AWS paginator safely. If the IAM user lacks permission,
        logs a warning and returns an empty list rather than failing the pipeline.
        """
        client = self.get_client(service_name, custom_region)
        kwargs = paginate_kwargs or {}
        items: List[Dict[str, Any]] = []

        try:
            paginator = client.get_paginator(operation_name)
            for page in paginator.paginate(**kwargs):
                for item in page.get(result_key, []):
                    items.append(item)
        except (ClientError, BotoCoreError) as err:
            if self._is_permission_error(err):
                logger.debug(
                    f"IAM permission denied for {service_name}:{operation_name} in {self.region}: {err}"
                )
            else:
                logger.error(f"Error paginating {service_name}:{operation_name} in {self.region}: {err}")
        except Exception as ex:
            logger.error(f"Unexpected error in {service_name}:{operation_name}: {ex}")

        return items

    def call(
        self,
        service_name: str,
        method_name: str,
        call_kwargs: Optional[Dict[str, Any]] = None,
        default: Any = None,
        custom_region: Optional[str] = None,
    ) -> Any:
        """
        Executes a direct boto3 client call with graceful degradation on permission denials.
        """
        client = self.get_client(service_name, custom_region)
        kwargs = call_kwargs or {}
        try:
            func = getattr(client, method_name)
            return func(**kwargs)
        except (ClientError, BotoCoreError) as err:
            if self._is_permission_error(err):
                logger.debug(
                    f"IAM permission denied calling {service_name}.{method_name}: {err}"
                )
            else:
                logger.error(f"Error calling {service_name}.{method_name}: {err}")
            return default if default is not None else {}
        except Exception as ex:
            logger.error(f"Unexpected error calling {service_name}.{method_name}: {ex}")
            return default if default is not None else {}

    @staticmethod
    def _is_permission_error(error: Exception) -> bool:
        msg = str(error).lower()
        return any(
            denial in msg
            for denial in [
                "accessdenied",
                "unauthorizedoperation",
                "not authorized",
                "explicit deny",
                "insufficientprivileges",
            ]
        )

    @staticmethod
    def parse_tags(tags: Optional[List[Dict[str, str]]]) -> Dict[str, str]:
        if not tags:
            return {}
        return {t.get("Key", ""): t.get("Value", "") for t in tags if t.get("Key")}
