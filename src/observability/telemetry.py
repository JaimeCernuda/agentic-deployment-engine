"""OpenTelemetry integration for distributed tracing.

Provides optional telemetry with W3C Trace Context propagation for
tracing requests across A2A agent boundaries.

Usage:
    from src.observability import setup_telemetry, traced_operation, inject_context

    # Initialize at startup (disabled by default)
    setup_telemetry(enabled=settings.otel_enabled)

    # Trace an operation
    with traced_operation("process_query", {"query.length": "100"}):
        result = await process(query)

    # Propagate context to downstream agents
    headers = inject_context({"Content-Type": "application/json"})
    response = await client.post(url, headers=headers)
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.trace import Span, Tracer

logger = logging.getLogger(__name__)

# Module state
_initialized = False
_tracer: Tracer | None = None


def setup_telemetry(
    service_name: str = "agentic-deployment-engine",
    endpoint: str | None = None,
    protocol: str = "grpc",
    enabled: bool = False,
) -> Tracer | None:
    """Configure OpenTelemetry with distributed tracing support.

    This function is safe to call multiple times - subsequent calls are no-ops.

    Args:
        service_name: Name for this service in traces.
        endpoint: OTLP collector endpoint. None uses console exporter.
        protocol: OTLP protocol - 'grpc' or 'http'.
        enabled: Whether to enable telemetry. False returns immediately.

    Returns:
        Configured tracer, or None if disabled or dependencies missing.
    """
    global _initialized, _tracer

    if not enabled:
        logger.debug("Telemetry disabled")
        return None

    if _initialized:
        return _tracer

    try:
        from opentelemetry import trace
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )
    except ImportError:
        logger.warning(
            "OpenTelemetry not installed. Install with: uv sync --extra otel"
        )
        return None

    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: service_name})

    # Create provider
    provider = TracerProvider(resource=resource)

    # Add exporter
    if endpoint:
        try:
            if protocol == "http":
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
            else:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(f"OTLP exporter configured: {endpoint} ({protocol})")
        except ImportError:
            logger.warning(
                f"OTLP {protocol} exporter not installed. "
                f"Install with: uv sync --extra otel"
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # Console exporter for development/debugging
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console span exporter configured (no endpoint specified)")

    trace.set_tracer_provider(provider)

    # Setup W3C Trace Context propagation
    propagator = CompositePropagator(
        [
            TraceContextTextMapPropagator(),
            W3CBaggagePropagator(),
        ]
    )
    set_global_textmap(propagator)

    # Instrument HTTP libraries if available
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.debug("HTTPX instrumentation enabled")
    except ImportError:
        pass

    # Instrument logging if available
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)
        logger.debug("Logging instrumentation enabled")
    except ImportError:
        pass

    _tracer = trace.get_tracer(__name__)
    _initialized = True

    logger.info(f"OpenTelemetry initialized for service: {service_name}")
    return _tracer


def instrument_fastapi(app: FastAPI) -> None:
    """Instrument a FastAPI app for tracing.

    Call this after creating the FastAPI app to enable automatic
    request/response tracing.

    Args:
        app: FastAPI application instance.
    """
    if not _initialized:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.debug(f"FastAPI instrumentation enabled for: {app.title}")
    except ImportError:
        logger.warning(
            "FastAPI instrumentation not available. Install with: uv sync --extra otel"
        )


def get_tracer() -> Tracer | None:
    """Get the configured tracer.

    Returns:
        The global tracer, or None if telemetry is disabled.
    """
    return _tracer


def inject_context(headers: dict[str, str]) -> dict[str, str]:
    """Inject trace context into outgoing HTTP headers.

    Call this before making A2A requests to propagate trace context.

    Args:
        headers: Existing headers dictionary (modified in place).

    Returns:
        The headers dictionary with trace context added.

    Example:
        headers = {"Content-Type": "application/json"}
        inject_context(headers)
        # headers now includes traceparent, tracestate
        response = await client.post(url, headers=headers)
    """
    if not _initialized:
        return headers

    try:
        from opentelemetry.propagate import inject

        inject(headers)
    except Exception as e:
        logger.debug(f"Failed to inject trace context: {e}")

    return headers


def extract_context(headers: dict[str, str]) -> Any:
    """Extract trace context from incoming HTTP headers.

    Call this when handling incoming A2A requests to continue the trace.

    Args:
        headers: Request headers dictionary.

    Returns:
        Context object to use with tracer.start_as_current_span(),
        or None if telemetry is disabled.

    Example:
        ctx = extract_context(dict(request.headers))
        with tracer.start_as_current_span("handle_request", context=ctx):
            # Process request
    """
    if not _initialized:
        return None

    try:
        from opentelemetry.propagate import extract

        return extract(headers)
    except Exception as e:
        logger.debug(f"Failed to extract trace context: {e}")
        return None


@contextmanager
def traced_operation(
    name: str,
    attributes: dict[str, str] | None = None,
) -> Generator[Span | None, None, None]:
    """Context manager for tracing an operation.

    Creates a new span for the duration of the context. Safe to use
    even when telemetry is disabled (yields None).

    Args:
        name: Name for this operation/span.
        attributes: Optional key-value attributes to attach to the span.

    Yields:
        The active span, or None if telemetry is disabled.

    Example:
        with traced_operation("process_query", {"query.length": "100"}):
            result = await process(query)
    """
    if not _tracer:
        yield None
        return

    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        yield span


def add_span_attribute(key: str, value: str) -> None:
    """Add an attribute to the current span.

    Safe to call when telemetry is disabled (no-op).

    Args:
        key: Attribute key.
        value: Attribute value.
    """
    if not _initialized:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)
    except Exception:
        pass


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span.

    Safe to call when telemetry is disabled (no-op).

    Args:
        exception: The exception to record.
    """
    if not _initialized:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span:
            span.record_exception(exception)
    except Exception:
        pass


def shutdown_telemetry() -> None:
    """Shutdown telemetry and flush pending spans.

    Call this during application shutdown to ensure all spans are exported.
    """
    global _initialized, _tracer

    if not _initialized:
        return

    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        shutdown_fn = getattr(provider, "shutdown", None)
        if shutdown_fn is not None:
            shutdown_fn()
            logger.info("Telemetry shutdown complete")
    except Exception as e:
        logger.error(f"Error during telemetry shutdown: {e}")

    _initialized = False
    _tracer = None
