"""
OpenTelemetry tracing setup for FastAPI.
Sends traces to Jaeger via OTLP gRPC (or stdout if Jaeger unavailable).
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "supply-chain-api")


def setup_tracing(app) -> None:
    """
    Configure OpenTelemetry tracing on the FastAPI app.
    Instruments all HTTP requests with trace/span metadata.
    Falls back to no-op if opentelemetry packages not installed.
    """
    if not OTEL_ENABLED:
        logger.info("OTEL_ENABLED=false — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        resource = Resource.create({"service.name": SERVICE_NAME, "service.version": "7.0.0"})
        provider = TracerProvider(resource=resource)

        # Try OTLP gRPC exporter (Jaeger)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OpenTelemetry → Jaeger OTLP at %s", OTEL_ENDPOINT)
        except Exception as e:
            # Fallback to console exporter
            logger.warning("OTLP exporter unavailable (%s) — using console exporter", e)
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing initialized for %s", SERVICE_NAME)

    except ImportError as e:
        logger.warning("opentelemetry not installed — tracing disabled: %s", e)


def get_tracer(name: str = SERVICE_NAME):
    """Get a tracer instance. Returns no-op tracer if OTEL not available."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        class _NoopTracer:
            def start_as_current_span(self, name, **kwargs):
                from contextlib import contextmanager
                @contextmanager
                def noop():
                    yield None
                return noop()
        return _NoopTracer()
