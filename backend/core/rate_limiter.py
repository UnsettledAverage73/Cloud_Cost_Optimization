"""
CloudPulse Production SRE Sliding-Window Rate Limiter Middleware
Protects backend infrastructure from denial-of-service, runaway LLM charges, and API abuse.
"""

import os
import time
import threading
from collections import deque
from typing import Dict, Tuple, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

# Configurable defaults
DEFAULT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_DEFAULT_MAX", "120"))  # per minute
HIGH_COMPUTE_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_HIGH_COMPUTE_MAX", "40"))  # per minute
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

HIGH_COMPUTE_PREFIXES = (
    "/api/v2/copilot/chat",
    "/api/v2/copilot/rag",
    "/api/v2/focus/query",
    "/api/v2/fleet/scan",
    "/api/v2/gitops/pr",
    "/api/v2/gitops/batch-pr",
)

EXCLUDED_PATHS = (
    "/healthz",
    "/readyz",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window log rate limiter with TTL auto-cleanup.
    """

    def __init__(self, window_seconds: int = WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self._history: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def is_allowed(self, client_key: str, max_requests: int) -> Tuple[bool, int, int]:
        """
        Evaluates if request is permitted under sliding window.
        Returns: (is_allowed, remaining_quota, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Periodic cleanup every 2 minutes
            if now - self._last_cleanup > 120:
                self._cleanup_expired(cutoff)
                self._last_cleanup = now

            if client_key not in self._history:
                self._history[client_key] = deque()

            timestamps = self._history[client_key]

            # Evict timestamps older than sliding window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                # Quota exhausted: retry after oldest item in window expires
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, 0, retry_after

            # Allow request and append timestamp
            timestamps.append(now)
            remaining = max(0, max_requests - len(timestamps))
            return True, remaining, 0

    def _cleanup_expired(self, cutoff: float):
        """Purges stale keys to prevent memory leak."""
        stale_keys = [k for k, q in self._history.items() if not q or q[-1] < cutoff]
        for k in stale_keys:
            del self._history[k]

    def reset(self):
        """Clears all tracking history (useful for test isolation)."""
        with self._lock:
            self._history.clear()


# Global limiter instance
rate_limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware enforcing tiered rate limits per client IP.
    """

    def __init__(self, app, enabled: Optional[bool] = None):
        super().__init__(app)
        # Enabled by default unless explicitly disabled via env or constructor
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Bypass rate limiting for SRE health probes, metrics, and documentation
        if path.startswith(EXCLUDED_PATHS):
            return await call_next(request)

        # Identify client by X-Forwarded-For or client host
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

        # Determine limit tier based on endpoint compute intensity
        if path.startswith(HIGH_COMPUTE_PREFIXES):
            max_limit = HIGH_COMPUTE_MAX_REQUESTS
            tier_key = f"{client_ip}:high_compute"
        else:
            max_limit = DEFAULT_MAX_REQUESTS
            tier_key = f"{client_ip}:default"

        allowed, remaining, retry_after = rate_limiter.is_allowed(tier_key, max_limit)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Maximum {max_limit} requests per minute allowed.",
                    "retry_after_seconds": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
