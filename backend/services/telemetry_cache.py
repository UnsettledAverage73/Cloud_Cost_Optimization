"""
CloudPulse Local Telemetry Cache Engine
Eliminates remote cold-start latency by caching normalized cloud telemetry locally.
Enables sub-50ms CLI response times with instant staleness checks and cache bypass.
"""
import time
import logging
from typing import Dict, Any, Optional

try:
    from collectors.fleet_cache import fleet_cache
except ImportError:
    from backend.collectors.fleet_cache import fleet_cache

logger = logging.getLogger("finops.services.cache")
CACHE_KEY_INVENTORY = "cli_inventory"


class TelemetryCacheManager:
    """
    High-performance telemetry cache for CLI operations.
    Saves and reads normalized cloud telemetry to avoid hitting remote servers repeatedly.
    """

    @staticmethod
    def get_cached_inventory(max_age_seconds: int = 900) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached cloud inventory if present and younger than max_age_seconds.
        Injects cache metadata (_cache_metadata) into returned dictionary.
        """
        entry = fleet_cache.get_entry(CACHE_KEY_INVENTORY)
        if not entry:
            return None

        cached_at = entry.get("cached_at", 0)
        age = time.time() - cached_at
        if age > max_age_seconds:
            return None

        data = entry.get("data")
        if data and isinstance(data, dict):
            # Create a shallow copy with metadata
            cached_data = dict(data)
            cached_data["_cache_metadata"] = {
                "served_from_cache": True,
                "cached_at": cached_at,
                "age_seconds": round(age, 1)
            }
            return cached_data
        return None

    @staticmethod
    def set_cached_inventory(inventory: Dict[str, Any], ttl_seconds: int = 900) -> None:
        """Stores inventory in persistent local cache with TTL."""
        if not inventory or not isinstance(inventory, dict):
            return
        # Strip internal cache metadata before persisting
        clean_inv = {k: v for k, v in inventory.items() if not k.startswith("_cache")}
        fleet_cache.set(CACHE_KEY_INVENTORY, clean_inv, ttl_seconds=ttl_seconds)
        logger.debug(f"Cached cloud inventory with TTL {ttl_seconds}s.")

    @staticmethod
    def invalidate(key: str = CACHE_KEY_INVENTORY) -> None:
        """Invalidates cached inventory."""
        fleet_cache.clear(key)
        logger.debug(f"Invalidated cache key: {key}")

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Returns statistics about current cache state."""
        entry = fleet_cache.get_entry(CACHE_KEY_INVENTORY)
        if not entry:
            return {"status": "empty", "age_seconds": None, "expires_in": None}
        now = time.time()
        age = round(now - entry.get("cached_at", now), 1)
        expires_in = max(0.0, round(entry.get("expires_at", now) - now, 1))
        return {
            "status": "cached" if expires_in > 0 else "expired",
            "age_seconds": age,
            "expires_in": expires_in
        }
