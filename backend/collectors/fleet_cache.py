"""
CloudPulse Fleet Inventory Cache & Asynchronous State
High-throughput caching layer ensuring instant sub-second responses, persistent disk caching, and background thread refreshes.
"""

import time
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("cloudpulse.fleet.cache")
CACHE_DIR = Path.home() / ".cloudpulse"
CACHE_FILE = CACHE_DIR / "fleet_cache.json"

class FleetStateCache:
    """
    Thread-safe cache with configurable TTL, persistent disk store, and non-blocking background refresh.
    """

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._refreshing = set()
        self._load_from_disk()

    def _load_from_disk(self):
        """Loads cached state from persistent disk if available."""
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, "r") as f:
                    disk_cache = json.load(f)
                    if isinstance(disk_cache, dict):
                        self._cache.update(disk_cache)
        except Exception as e:
            logger.debug(f"Could not load cache from disk: {e}")

    def _save_to_disk(self):
        """Persists memory cache to disk."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(self._cache, f)
        except Exception as e:
            logger.debug(f"Could not persist cache to disk: {e}")

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            # Return value even if expired (stale-while-revalidate pattern)
            return entry.get("data")

    def is_stale(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return True
            return time.time() > entry.get("expires_at", 0)

    def set(self, key: str, data: Any, ttl_seconds: Optional[int] = None):
        ttl = ttl_seconds or self.default_ttl
        with self._lock:
            self._cache[key] = {
                "data": data,
                "cached_at": time.time(),
                "expires_at": time.time() + ttl
            }
            self._save_to_disk()

    def trigger_async_refresh(self, key: str, refresh_fn, *args, **kwargs):
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)

        def _worker():
            try:
                logger.info(f"Background async refresh started for key '{key}'...")
                res = refresh_fn(*args, **kwargs)
                if res:
                    self.set(key, res)
                logger.info(f"Background async refresh completed for key '{key}'.")
            except Exception as e:
                logger.error(f"Error during async refresh for key '{key}': {e}")
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

# Global Singleton
fleet_cache = FleetStateCache()

