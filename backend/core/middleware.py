"""
CloudPulse Production SRE Middleware
Provides request correlation IDs, latency measurement, structured observability headers,
and Prometheus metrics collection.
"""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from core.metrics import record_request_metric, ACTIVE_REQUESTS
    from core.logging import correlation_id_ctx
except ImportError:
    try:
        from backend.core.metrics import record_request_metric, ACTIVE_REQUESTS
        from backend.core.logging import correlation_id_ctx
    except ImportError:
        record_request_metric = None
        ACTIVE_REQUESTS = None
        correlation_id_ctx = None

logger = logging.getLogger("cloudpulse.sre.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Google SRE Correlation ID & Observability Middleware:
    - Extracts or generates a unique X-Request-ID for distributed tracing.
    - Measures wall-clock execution time and appends X-Process-Time header.
    - Records Prometheus HTTP counter and latency histograms.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        if correlation_id_ctx:
            correlation_id_ctx.set(request_id)

        if ACTIVE_REQUESTS:
            ACTIVE_REQUESTS.inc()

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_sec = time.perf_counter() - start_time
            duration_ms = round(duration_sec * 1000, 2)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration_ms}ms"

            # Record Prometheus metrics
            if record_request_metric and not request.url.path.startswith(("/healthz", "/readyz", "/metrics")):
                record_request_metric(request.method, request.url.path, response.status_code, duration_sec)

            # Fast SRE access log
            if not request.url.path.startswith(("/healthz", "/readyz", "/metrics")):
                logger.info(
                    f"[{request_id}] {request.method} {request.url.path} "
                    f"status={response.status_code} duration={duration_ms}ms"
                )

            return response
        finally:
            if ACTIVE_REQUESTS:
                ACTIVE_REQUESTS.dec()
