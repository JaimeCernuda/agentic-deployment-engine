"""Tests for semantic observability module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.observability.semantic import (
    JSONFileExporter,
    SemanticTracer,
    SpanContext,
    SpanData,
    get_semantic_tracer,
    reset_semantic_tracer,
)


class TestSpanData:
    """Tests for SpanData dataclass."""

    def test_span_data_creation(self) -> None:
        """SpanData should store all fields correctly."""
        span = SpanData(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="parent-789",
            name="test_span",
            level="agent",
            category="tool_call",
            start_time="2026-01-01T00:00:00Z",
        )

        assert span.trace_id == "trace-123"
        assert span.span_id == "span-456"
        assert span.parent_span_id == "parent-789"
        assert span.name == "test_span"
        assert span.level == "agent"
        assert span.category == "tool_call"
        assert span.status == "ok"
        assert span.error_message is None
        assert span.attributes == {}
        assert span.events == []

    def test_span_data_with_error(self) -> None:
        """SpanData should store error status correctly."""
        span = SpanData(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id=None,
            name="error_span",
            level="a2a",
            category="message_exchange",
            start_time="2026-01-01T00:00:00Z",
            status="error",
            error_message="Something went wrong",
        )

        assert span.status == "error"
        assert span.error_message == "Something went wrong"


class TestSpanContext:
    """Tests for SpanContext thread-local storage."""

    def test_get_current_returns_none_when_empty(self) -> None:
        """get_current() should return None when no span is set."""
        SpanContext.set_current(None)
        assert SpanContext.get_current() is None

    def test_set_and_get_current(self) -> None:
        """set_current() and get_current() should work correctly."""
        span = SpanData(
            trace_id="test",
            span_id="test",
            parent_span_id=None,
            name="test",
            level="agent",
            category="test",
            start_time="2026-01-01T00:00:00Z",
        )

        SpanContext.set_current(span)
        assert SpanContext.get_current() == span

        SpanContext.set_current(None)
        assert SpanContext.get_current() is None


class TestJSONFileExporter:
    """Tests for JSONFileExporter."""

    def test_creates_output_directory(self) -> None:
        """Exporter should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "traces" / "nested"
            JSONFileExporter(output_dir)  # Creating exporter creates the directory

            assert output_dir.exists()

    def test_start_trace_creates_file_path(self) -> None:
        """start_trace() should set up current file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = JSONFileExporter(tmpdir)
            exporter.start_trace("trace-123", "my-trace")

            assert exporter._current_file is not None
            assert "my-trace" in str(exporter._current_file)

    def test_export_span_writes_to_file(self) -> None:
        """export_span() should write span data to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = JSONFileExporter(tmpdir)
            exporter.start_trace("trace-123", "test-trace")

            span = SpanData(
                trace_id="trace-123",
                span_id="span-456",
                parent_span_id=None,
                name="test_span",
                level="agent",
                category="tool_call",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
                duration_ms=1000,
            )

            exporter.export_span(span)

            # Read the file and verify content
            with open(exporter._current_file) as f:
                data = json.load(f)

            assert data["span_count"] == 1
            assert len(data["spans"]) == 1
            assert data["spans"][0]["name"] == "test_span"


class TestSemanticTracer:
    """Tests for SemanticTracer."""

    def test_disabled_tracer(self) -> None:
        """Disabled tracer should not create exporter."""
        tracer = SemanticTracer(enabled=False)

        assert tracer.enabled is False
        assert tracer.exporter is None

    def test_enabled_tracer_with_output_dir(self) -> None:
        """Enabled tracer should create exporter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(
                service_name="test-service",
                output_dir=tmpdir,
                enabled=True,
            )

            assert tracer.enabled is True
            assert tracer.exporter is not None

    def test_start_trace_returns_trace_id(self) -> None:
        """start_trace() should return a trace ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            trace_id = tracer.start_trace("my-trace")

            assert trace_id is not None
            assert len(trace_id) > 0

    def test_job_deployment_span(self) -> None:
        """job_deployment() should create framework-level span."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.job_deployment(
                job_id="job-123",
                job_name="Test Job",
                agents=["agent1", "agent2"],
                topology="hub-spoke",
            ) as span:
                assert span.level == "framework"
                assert span.category == "job_deployment"
                assert span.attributes["job.id"] == "job-123"

    def test_query_handling_span(self) -> None:
        """query_handling() should create agent-level span."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.query_handling(
                agent_name="test-agent",
                query="What is the weather?",
                session_id="session-123",
                history_length=5,
            ) as span:
                assert span.level == "agent"
                assert span.category == "query_handling"
                assert span.attributes["query.agent"] == "test-agent"

    def test_tool_call_span(self) -> None:
        """tool_call() should create agent-level span."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call(
                tool_name="get_weather",
                tool_input={"city": "Tokyo"},
            ) as span:
                assert span.level == "agent"
                assert span.category == "tool_call"
                assert span.attributes["tool.name"] == "get_weather"

    def test_record_tool_result(self) -> None:
        """record_tool_result() should update span attributes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call("test_tool", {}) as span:
                tracer.record_tool_result(span, {"temp": 22.5}, success=True)

            assert span.attributes["tool.success"] is True
            assert "temp" in span.attributes["tool.result"]

    def test_a2a_message_span(self) -> None:
        """a2a_message() should create A2A-level span."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.a2a_message(
                source_agent="controller",
                target_agent="weather",
                query="Get weather",
            ) as span:
                assert span.level == "a2a"
                assert span.category == "message_exchange"

    def test_disabled_tracer_yields_dummy_span(self) -> None:
        """Disabled tracer should yield a dummy span."""
        tracer = SemanticTracer(enabled=False)

        with tracer.tool_call("test", {}) as span:
            assert span.trace_id == "disabled"

    def test_get_trace_file(self) -> None:
        """get_trace_file() should return current trace file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call("test", {}):
                pass

            trace_file = tracer.get_trace_file()
            assert trace_file is not None
            assert trace_file.exists()


class TestGetSemanticTracer:
    """Tests for global tracer getter."""

    def test_returns_same_instance(self) -> None:
        """get_semantic_tracer() should return the same instance."""
        reset_semantic_tracer()

        tracer1 = get_semantic_tracer()
        tracer2 = get_semantic_tracer()

        assert tracer1 is tracer2

    def test_respects_environment_variables(self) -> None:
        """get_semantic_tracer() should read from environment."""
        reset_semantic_tracer()

        with patch.dict(
            os.environ,
            {
                "AGENT_SEMANTIC_TRACING_ENABLED": "false",
            },
        ):
            tracer = get_semantic_tracer()
            assert tracer.enabled is False

        reset_semantic_tracer()

    def test_reset_creates_new_instance(self) -> None:
        """reset_semantic_tracer() should allow creating new instance."""
        tracer1 = get_semantic_tracer()
        reset_semantic_tracer()
        tracer2 = get_semantic_tracer()

        assert tracer1 is not tracer2
