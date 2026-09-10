"""
OpenTelemetry Distributed Tracing
Instruments FastAPI routes, Celery workers, and GPU inference calls.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request


# ========================== Trace Context =======================

class TraceContext:
    """Manages distributed trace context across services."""

    def generate_trace_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")

    def generate_span_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")[:16]

    def extract_trace_id(self, request: Request) -> str:
        """Extract or generate trace ID from request headers."""
        return (
            request.headers.get("X-Trace-ID") or
            request.headers.get("X-Request-ID") or
            self.generate_trace_id()
        )


class TracingService:
    """OpenTelemetry distributed tracing service."""

    def __init__(self):
        self.context = TraceContext()
        self._otel_enabled = False
        self._setup_otel()

    def _setup_otel(self):
        """Setup OpenTelemetry if available."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("modelens.backend")
            self._otel_enabled = True
            print("[Tracing] OpenTelemetry initialized")
        except ImportError:
            print("[Tracing] OpenTelemetry not installed - using fallback")
            self._otel_enabled = False

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> dict:
        """Start a new trace span."""
        span_id = self.context.generate_span_id()
        trace_id = trace_id or self.context.generate_trace_id()

        span = {
            "trace_id": trace_id,
            "span_id": span_id,
            "name": name,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        }

        if self._otel_enabled:
            try:
                with self._tracer.start_as_current_span(name) as otel_span:
                    if attributes:
                        for k, v in attributes.items():
                            otel_span.set_attribute(k, str(v))
            except Exception:
                pass

        return span

    def end_span(self, span: dict, status: str = "OK", error: Optional[str] = None) -> dict:
        """End a trace span."""
        span["end_time"] = datetime.now(timezone.utc).isoformat()
        span["status"] = status
        if error:
            span["error"] = error[:200]
        return span

    def trace_job(
        self,
        job_type: str,
        job_id: int,
        brand_id: int,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Create trace span for a generation job."""
        return self.start_span(
            name=f"job.{job_type}",
            trace_id=trace_id,
            attributes={
                "job.type": job_type,
                "job.id": str(job_id),
                "brand.id": str(brand_id),
                "service.name": "modelens-worker",
            }
        )

    def get_trace_headers(self, trace_id: str) -> dict:
        """Get trace headers to propagate to downstream services."""
        return {
            "X-Trace-ID": trace_id,
            "X-Span-ID": self.context.generate_span_id(),
            "X-Service": "modelens-backend",
        }


# FastAPI middleware
async def tracing_middleware(request: Request, call_next):
    """FastAPI middleware to inject trace IDs."""
    context = TraceContext()
    trace_id = context.extract_trace_id(request)
    request.state.trace_id = trace_id

    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


# Singleton
tracing_service = TracingService()
