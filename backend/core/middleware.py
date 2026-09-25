"""
CloudPulse Production SRE Middleware
Provides request correlation IDs, latency measurement, and structured observability headers.
"""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("cloudpulse.sre.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Google SRE Correlation ID & Timing Middleware:
    - Extracts or generates a unique X-Request-ID for distributed tracing.
    - Measures wall-clock execution time and appends X-Process-Time header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms}ms"

        # Fast SRE access log
        if not request.url.path.startswith(("/healthz", "/readyz", "/metrics")):
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"status={response.status_code} duration={duration_ms}ms"
            )

        return response
