"""
CloudPulse FinOps RAG Query Cache
Sub-millisecond query caching layer with TTL, inventory fingerprinting, and disk persistence.
"""

import time
import json
import hashlib
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("cloudpulse.ai.query_cache")

QUERY_CACHE_DIR = Path.home() / ".cloudpulse"
QUERY_CACHE_FILE = QUERY_CACHE_DIR / "rag_query_cache.json"


class FinOpsQueryCache:
    """
    Thread-safe query response cache:
    - Serves repeated or frequent inquiries in sub-millisecond time (< 5ms)
    - Automatically invalidates if underlying cloud inventory fingerprint changes
    - Persists across CLI invocations to disk
    """

    def __init__(self, default_ttl_seconds: int = 600):
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_queries": 0
        }
        self._load_from_disk()

    def _generate_key(self, query: str, inventory_fingerprint: str = "") -> str:
        norm_q = " ".join((query or "").lower().strip().split())
        raw = f"{norm_q}:{inventory_fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_from_disk(self):
        try:
            if QUERY_CACHE_FILE.exists():
                with open(QUERY_CACHE_FILE, "r") as f:
                    data = json.load(f)
                    now = time.time()
                    # Filter out expired entries on startup
                    valid_cache = {
                        k: v for k, v in data.get("cache", {}).items()
                        if v.get("expires_at", 0) > now
                    }
                    self._cache.update(valid_cache)
                    self.stats["hits"] = data.get("stats", {}).get("hits", 0)
                    self.stats["misses"] = data.get("stats", {}).get("misses", 0)
                    self.stats["total_queries"] = self.stats["hits"] + self.stats["misses"]
        except Exception as e:
            logger.debug(f"Could not load query cache from disk: {e}")

    def _save_to_disk(self):
        try:
            QUERY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(QUERY_CACHE_FILE, "w") as f:
                json.dump({
                    "cache": self._cache,
                    "stats": self.stats
                }, f)
        except Exception as e:
            logger.debug(f"Could not save query cache to disk: {e}")

    def get(self, query: str, inventory_fingerprint: str = "") -> Optional[Dict[str, Any]]:
        """Retrieves a cached RAG response if present and unexpired."""
        key = self._generate_key(query, inventory_fingerprint)
        with self._lock:
            self.stats["total_queries"] += 1
            entry = self._cache.get(key)
            if not entry:
                self.stats["misses"] += 1
                return None

            if time.time() > entry.get("expires_at", 0):
                # Expired
                del self._cache[key]
                self.stats["misses"] += 1
                return None

            self.stats["hits"] += 1
            cached_resp = dict(entry["response"])
            cached_resp["cached"] = True
            cached_resp["cache_hit"] = True
            return cached_resp

    def set(
        self,
        query: str,
        response: Dict[str, Any],
        inventory_fingerprint: str = "",
        ttl_seconds: Optional[int] = None
    ):
        """Caches a RAG response with TTL."""
        key = self._generate_key(query, inventory_fingerprint)
        ttl = ttl_seconds or self.default_ttl
        now = time.time()
        with self._lock:
            self._cache[key] = {
                "query": query,
                "response": response,
                "cached_at": now,
                "expires_at": now + ttl
            }
            self._save_to_disk()

    def clear(self):
        """Purges all cached query responses."""
        with self._lock:
            self._cache.clear()
            self._save_to_disk()

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry including hit rates."""
        with self._lock:
            total = self.stats["total_queries"]
            hits = self.stats["hits"]
            hit_rate = round((hits / total * 100.0), 2) if total > 0 else 0.0
            return {
                "total_queries": total,
                "hits": hits,
                "misses": self.stats["misses"],
                "hit_rate_percent": hit_rate,
                "active_cached_entries": len(self._cache)
            }


# Global Singleton
query_cache = FinOpsQueryCache()
