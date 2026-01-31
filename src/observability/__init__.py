"""Observability: logging, telemetry, and semantic tracing."""

from .logging import get_logger, setup_logging
from .semantic import SemanticTracer, get_current_agent_name, get_semantic_tracer
from .telemetry import (
    add_span_attribute,
    extract_context,
    inject_context,
    instrument_fastapi,
    record_exception,
    setup_telemetry,
    shutdown_telemetry,
    traced_operation,
)

__all__ = [
    # Logging
    "get_logger",
    "setup_logging",
    # Telemetry
    "add_span_attribute",
    "extract_context",
    "inject_context",
    "instrument_fastapi",
    "record_exception",
    "setup_telemetry",
    "shutdown_telemetry",
    "traced_operation",
    # Semantic Tracing
    "SemanticTracer",
    "get_current_agent_name",
    "get_semantic_tracer",
]
