"""Tests for semantic observability module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.observability.semantic import (
    JSONFileExporter,
    SemanticTracer,
    SpanContext,
    SpanData,
    get_current_agent_name,
    get_semantic_tracer,
    merge_job_traces,
    reset_semantic_tracer,
    write_unified_trace,
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


class TestMergeJobTraces:
    """Tests for merge_job_traces() function."""

    def test_merge_nonexistent_directory_returns_none(self) -> None:
        """merge_job_traces() should return None for nonexistent directory."""
        result = merge_job_traces("/nonexistent/path/to/traces")
        assert result is None

    def test_merge_empty_directory_returns_none(self) -> None:
        """merge_job_traces() should return None for directory with no traces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = merge_job_traces(tmpdir)
            assert result is None

    def test_merge_single_trace_file(self) -> None:
        """merge_job_traces() should work with single trace file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a single trace file
            trace_data = {
                "trace_id": "trace-123",
                "service_name": "agent1",
                "span_count": 2,
                "spans": [
                    {
                        "trace_id": "trace-123",
                        "span_id": "span-1",
                        "name": "tool:get_weather",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {"agent.name": "Weather Agent"},
                    },
                    {
                        "trace_id": "trace-123",
                        "span_id": "span-2",
                        "name": "llm:assistant",
                        "start_time": "2026-01-01T00:00:01Z",
                        "attributes": {"agent.name": "Weather Agent"},
                    },
                ],
            }
            trace_file = Path(tmpdir) / "trace_123_agent1.json"
            with open(trace_file, "w") as f:
                json.dump(trace_data, f)

            result = merge_job_traces(tmpdir)

            assert result is not None
            assert result["span_count"] == 2
            assert result["source_files"] == 1
            assert "Weather Agent" in result["agents"]
            assert len(result["spans"]) == 2

    def test_merge_multiple_trace_files(self) -> None:
        """merge_job_traces() should merge spans from multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two trace files with different agents
            trace1 = {
                "trace_id": "trace-abc",
                "service_name": "controller",
                "span_count": 1,
                "spans": [
                    {
                        "trace_id": "trace-abc",
                        "span_id": "span-1",
                        "name": "query:Controller",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {"agent.name": "Controller Agent"},
                    },
                ],
            }
            trace2 = {
                "trace_id": "trace-abc",
                "service_name": "worker",
                "span_count": 2,
                "spans": [
                    {
                        "trace_id": "trace-abc",
                        "span_id": "span-2",
                        "name": "tool:process",
                        "start_time": "2026-01-01T00:00:02Z",
                        "attributes": {"agent.name": "Worker Agent"},
                    },
                    {
                        "trace_id": "trace-abc",
                        "span_id": "span-3",
                        "name": "llm:assistant",
                        "start_time": "2026-01-01T00:00:03Z",
                        "attributes": {"agent.name": "Worker Agent"},
                    },
                ],
            }

            with open(Path(tmpdir) / "trace_abc_controller.json", "w") as f:
                json.dump(trace1, f)
            with open(Path(tmpdir) / "trace_abc_worker.json", "w") as f:
                json.dump(trace2, f)

            result = merge_job_traces(tmpdir)

            assert result is not None
            assert result["span_count"] == 3
            assert result["source_files"] == 2
            assert "Controller Agent" in result["agents"]
            assert "Worker Agent" in result["agents"]
            # Spans should be sorted by start_time
            assert result["spans"][0]["name"] == "query:Controller"
            assert result["spans"][2]["name"] == "llm:assistant"

    def test_merge_handles_invalid_json_gracefully(self) -> None:
        """merge_job_traces() should skip invalid JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create one valid and one invalid trace file
            valid_trace = {
                "trace_id": "trace-123",
                "spans": [
                    {
                        "trace_id": "trace-123",
                        "span_id": "span-1",
                        "name": "test",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {"agent.name": "Test Agent"},
                    },
                ],
            }
            with open(Path(tmpdir) / "trace_123_valid.json", "w") as f:
                json.dump(valid_trace, f)
            with open(Path(tmpdir) / "trace_invalid.json", "w") as f:
                f.write("not valid json {{{")

            result = merge_job_traces(tmpdir)

            assert result is not None
            assert result["span_count"] == 1
            assert result["source_files"] == 2  # Counted even if invalid

    def test_merge_collects_multiple_trace_ids(self) -> None:
        """merge_job_traces() should collect all unique trace IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace1 = {
                "spans": [
                    {
                        "trace_id": "trace-A",
                        "span_id": "1",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {},
                    },
                    {
                        "trace_id": "trace-B",
                        "span_id": "2",
                        "start_time": "2026-01-01T00:00:01Z",
                        "attributes": {},
                    },
                ],
            }
            with open(Path(tmpdir) / "trace_mixed.json", "w") as f:
                json.dump(trace1, f)

            result = merge_job_traces(tmpdir)

            assert result is not None
            assert "trace-A" in result["trace_ids"]
            assert "trace-B" in result["trace_ids"]


class TestWriteUnifiedTrace:
    """Tests for write_unified_trace() function."""

    def test_write_returns_none_for_empty_directory(self) -> None:
        """write_unified_trace() should return None for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_unified_trace(tmpdir)
            assert result is None

    def test_write_creates_unified_trace_file(self) -> None:
        """write_unified_trace() should create unified_trace.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a trace file
            trace_data = {
                "trace_id": "trace-123",
                "spans": [
                    {
                        "trace_id": "trace-123",
                        "span_id": "span-1",
                        "name": "test_span",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {"agent.name": "Test Agent"},
                    },
                ],
            }
            with open(Path(tmpdir) / "trace_123_test.json", "w") as f:
                json.dump(trace_data, f)

            result = write_unified_trace(tmpdir)

            assert result is not None
            assert result.name == "unified_trace.json"
            assert result.exists()

            # Verify file content
            with open(result) as f:
                unified = json.load(f)
            assert unified["span_count"] == 1
            assert "Test Agent" in unified["agents"]

    def test_write_returns_path_object(self) -> None:
        """write_unified_trace() should return a Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_data = {
                "spans": [
                    {
                        "trace_id": "t",
                        "span_id": "s",
                        "start_time": "2026-01-01T00:00:00Z",
                        "attributes": {},
                    },
                ],
            }
            with open(Path(tmpdir) / "trace_t.json", "w") as f:
                json.dump(trace_data, f)

            result = write_unified_trace(tmpdir)

            assert isinstance(result, Path)
            assert str(result).endswith("unified_trace.json")


class TestSemanticTracerAdditional:
    """Additional tests for improved coverage."""

    def test_agent_discovery_span(self) -> None:
        """agent_discovery() should create A2A-level span."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.agent_discovery(
                agent_url="http://localhost:9001",
                discovered_skills=["weather", "forecast"],
            ) as span:
                assert span.level == "a2a"
                assert span.category == "discovery"
                assert span.attributes["discovery.url"] == "http://localhost:9001"
                assert span.attributes["discovery.skills"] == ["weather", "forecast"]

    def test_record_a2a_response(self) -> None:
        """record_a2a_response() should update span attributes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.a2a_message(
                source_agent="controller",
                target_agent="worker",
                query="test",
            ) as span:
                tracer.record_a2a_response(
                    span,
                    response="OK response",
                    status_code=200,
                    tools_used=["tool1", "tool2"],
                )

            assert span.attributes["a2a.response"] == "OK response"
            assert span.attributes["a2a.status_code"] == 200
            assert span.attributes["a2a.tools_used"] == ["tool1", "tool2"]

    def test_get_trace_id(self) -> None:
        """get_trace_id() should return current trace ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)

            assert tracer.get_trace_id() is None

            trace_id = tracer.start_trace("test")
            assert tracer.get_trace_id() == trace_id

    def test_continue_trace(self) -> None:
        """continue_trace() should set trace ID for correlation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)

            parent_trace_id = "parent-trace-123"
            tracer.continue_trace(parent_trace_id)

            assert tracer.get_trace_id() == parent_trace_id

    def test_tool_call_with_string_input(self) -> None:
        """tool_call() should handle string input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call("my_tool", "simple string input") as span:
                assert span.attributes["tool.input"] == "simple string input"

    def test_tool_call_with_none_input(self) -> None:
        """tool_call() should handle None input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call("my_tool", None) as span:
                assert span.attributes["tool.input"] is None

    def test_record_tool_result_with_non_dict(self) -> None:
        """record_tool_result() should handle non-dict results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.tool_call("test_tool", {}) as span:
                tracer.record_tool_result(span, "simple string result", success=True)

            assert span.attributes["tool.result"] == "simple string result"
            assert span.attributes["tool.success"] is True

    def test_llm_message_span(self) -> None:
        """llm_message() should create agent-level span with model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with tracer.llm_message(
                role="user",
                content="Hello there!",
                model="claude-3",
            ) as span:
                assert span.level == "agent"
                assert span.category == "llm_message"
                assert span.attributes["llm.role"] == "user"
                assert span.attributes["llm.model"] == "claude-3"

    def test_span_exception_propagation(self) -> None:
        """_span_context should capture exceptions and propagate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            with pytest.raises(ValueError, match="Test exception"):
                with tracer.tool_call("failing_tool", {}) as span:
                    raise ValueError("Test exception")

            # Span should have error status
            assert span.status == "error"
            assert "Test exception" in span.error_message

    def test_get_trace_file_returns_none_without_exporter(self) -> None:
        """get_trace_file() should return None when no exporter."""
        tracer = SemanticTracer(enabled=False)
        assert tracer.get_trace_file() is None

    def test_auto_trace_id_generation_in_create_span(self) -> None:
        """_create_span should auto-generate trace_id if not set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            # Don't call start_trace - let _create_span auto-generate

            with tracer.tool_call("test_tool", {}) as span:
                assert span.trace_id is not None
                assert len(span.trace_id) > 0

    def test_start_trace_with_parent_id(self) -> None:
        """start_trace() with parent_trace_id should use that ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            parent_id = "parent-abc-123"

            trace_id = tracer.start_trace("child-trace", parent_trace_id=parent_id)

            assert trace_id == parent_id
            assert tracer.get_trace_id() == parent_id

    def test_get_current_agent_name_returns_none_by_default(self) -> None:
        """get_current_agent_name() should return None when not in query context."""
        assert get_current_agent_name() is None

    def test_query_handling_sets_agent_name_context(self) -> None:
        """query_handling() should set agent name in context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = SemanticTracer(output_dir=tmpdir, enabled=True)
            tracer.start_trace("test")

            # Before query context
            assert get_current_agent_name() is None

            with tracer.query_handling(
                agent_name="Test Agent",
                query="Hello",
            ):
                # Inside query context
                assert get_current_agent_name() == "Test Agent"

            # After query context
            assert get_current_agent_name() is None

    def test_exporter_write_file_without_current_file(self) -> None:
        """_write_file() should return early if no current file set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = JSONFileExporter(tmpdir)
            # Don't call start_trace, so _current_file is None
            # This should not raise
            exporter._write_file()
            assert exporter._current_file is None
