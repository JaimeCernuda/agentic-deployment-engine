"""Integration tests for failure mode tracing.

Verifies that semantic traces properly capture error states for:
- A2A timeout errors
- HTTP errors from target agents
- Agent crashes mid-request
"""

import json
import os
from pathlib import Path

import pytest

from src.observability.semantic import (
    SemanticTracer,
    read_ndjson_trace,
    reset_semantic_tracer,
)


class TestFailureModeTracing:
    """Test that failure modes are properly traced."""

    @pytest.fixture(autouse=True)
    def setup_tracer(self, tmp_path: Path) -> None:
        """Set up a fresh tracer for each test."""
        reset_semantic_tracer()
        # Create tracer with temp directory
        self.trace_dir = tmp_path / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        os.environ["AGENT_SEMANTIC_TRACING_ENABLED"] = "true"
        os.environ["AGENT_SEMANTIC_TRACE_DIR"] = str(self.trace_dir)

        yield

        # Cleanup
        reset_semantic_tracer()
        os.environ.pop("AGENT_SEMANTIC_TRACING_ENABLED", None)
        os.environ.pop("AGENT_SEMANTIC_TRACE_DIR", None)

    def _read_trace_file(self) -> dict | None:
        """Read the most recent trace file (supports both JSON and NDJSON formats)."""
        # Try NDJSON first (new format)
        ndjson_files = list(self.trace_dir.glob("*.ndjson"))
        if ndjson_files:
            latest = max(ndjson_files, key=lambda p: p.stat().st_mtime)
            return read_ndjson_trace(latest)

        # Fall back to legacy JSON format
        json_files = list(self.trace_dir.glob("trace_*.json"))
        if json_files:
            latest = max(json_files, key=lambda p: p.stat().st_mtime)
            return json.loads(latest.read_text())

        return None

    def _find_span_by_name(self, trace: dict, name_pattern: str) -> dict | None:
        """Find a span by name pattern."""
        for span in trace.get("spans", []):
            if name_pattern in span.get("name", ""):
                return span
        return None

    @pytest.mark.asyncio
    async def test_timeout_error_pattern_traced(self) -> None:
        """Verify timeout error pattern is captured in traces.

        This tests the pattern used in A2A transport for timeout errors.
        The actual transport uses SDK MCP tools which require different testing.
        """
        # Use a local tracer instance with the test directory
        tracer = SemanticTracer(
            service_name="test",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-timeout")

        # Simulate the pattern used in transport.py for timeouts
        with tracer.a2a_message(
            source_agent="controller",
            target_agent="worker",
            query="test query that times out",
        ) as sem_span:
            # Simulate timeout error handling
            sem_span.status = "error"
            sem_span.error_message = "Request timed out"

        # Verify trace captured the error
        trace = self._read_trace_file()
        assert trace is not None, "Trace file should be written"

        # Find the A2A span
        a2a_span = self._find_span_by_name(trace, "a2a:")
        assert a2a_span is not None, "A2A span should exist"
        assert a2a_span["status"] == "error"
        assert a2a_span["error_message"] == "Request timed out"

    @pytest.mark.asyncio
    async def test_http_error_pattern_traced(self) -> None:
        """Verify HTTP error pattern is captured in traces.

        Tests the error handling pattern for HTTP status errors.
        """
        tracer = SemanticTracer(
            service_name="test",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-http-error")

        # Simulate the pattern used in transport.py for HTTP errors
        with tracer.a2a_message(
            source_agent="controller",
            target_agent="worker",
            query="test query that fails",
        ) as sem_span:
            # Simulate HTTP 500 error handling
            sem_span.status = "error"
            sem_span.error_message = "HTTP 500"

        # Verify trace captured the error
        trace = self._read_trace_file()
        assert trace is not None

        a2a_span = self._find_span_by_name(trace, "a2a:")
        assert a2a_span is not None
        assert a2a_span["status"] == "error"
        assert "HTTP 500" in a2a_span["error_message"]

    @pytest.mark.asyncio
    async def test_connection_error_pattern_traced(self) -> None:
        """Verify connection error pattern is captured in traces."""
        tracer = SemanticTracer(
            service_name="test",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-connection-refused")

        # Simulate connection refused error
        with tracer.a2a_message(
            source_agent="controller",
            target_agent="dead_worker",
            query="test query to dead agent",
        ) as sem_span:
            sem_span.status = "error"
            sem_span.error_message = "Connection refused"

        # Verify trace captured the error
        trace = self._read_trace_file()
        assert trace is not None

        a2a_span = self._find_span_by_name(trace, "a2a:")
        assert a2a_span is not None
        assert a2a_span["status"] == "error"
        assert "Connection refused" in a2a_span["error_message"]

    @pytest.mark.asyncio
    async def test_semantic_tracer_error_context_manager(self) -> None:
        """Verify context manager properly captures errors."""
        tracer = SemanticTracer(
            service_name="test",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-context-error")

        # Use context manager with an exception
        with pytest.raises(ValueError, match="Test error"):
            with tracer.tool_call("failing_tool", {"input": "test"}):
                raise ValueError("Test error")

        # Verify trace captured the error
        trace = self._read_trace_file()
        assert trace is not None

        tool_span = self._find_span_by_name(trace, "tool:failing_tool")
        assert tool_span is not None
        assert tool_span["status"] == "error"
        assert "Test error" in tool_span["error_message"]
        assert tool_span["duration_ms"] is not None
        assert tool_span["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_a2a_message_records_error_status(self) -> None:
        """Verify A2A span error attributes are set correctly."""
        tracer = SemanticTracer(
            service_name="test",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-a2a-error-status")

        # Manually test the a2a_message span with error
        with tracer.a2a_message(
            source_agent="controller",
            target_agent="worker",
            query="test query",
        ) as span:
            # Simulate error
            span.status = "error"
            span.error_message = "Agent unreachable"

        # Verify trace
        trace = self._read_trace_file()
        assert trace is not None

        a2a_span = self._find_span_by_name(trace, "a2a:controller->worker")
        assert a2a_span is not None
        assert a2a_span["status"] == "error"
        assert a2a_span["error_message"] == "Agent unreachable"
        assert a2a_span["attributes"]["a2a.source"] == "controller"
        assert a2a_span["attributes"]["a2a.target"] == "worker"


class TestTraceFileIntegrity:
    """Test that trace files are written correctly on errors."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path) -> None:
        """Set up test environment."""
        reset_semantic_tracer()
        self.trace_dir = tmp_path / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)

        yield

        reset_semantic_tracer()

    def _read_trace_file(self) -> dict | None:
        """Read the most recent trace file (supports both JSON and NDJSON formats)."""
        # Try NDJSON first (new format)
        ndjson_files = list(self.trace_dir.glob("*.ndjson"))
        if ndjson_files:
            latest = max(ndjson_files, key=lambda p: p.stat().st_mtime)
            return read_ndjson_trace(latest)

        # Fall back to legacy JSON format
        json_files = list(self.trace_dir.glob("trace_*.json"))
        if json_files:
            latest = max(json_files, key=lambda p: p.stat().st_mtime)
            return json.loads(latest.read_text())

        return None

    def test_trace_file_written_even_on_error(self) -> None:
        """Verify trace file is written even when spans error."""
        tracer = SemanticTracer(
            service_name="test-integrity",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-file-on-error")

        # Create several spans, some with errors
        with tracer.job_deployment("job-1", "test-job", ["agent1"]):
            pass

        with pytest.raises(RuntimeError):
            with tracer.agent_lifecycle("agent1", "Test Agent", "start"):
                raise RuntimeError("Startup failed")

        # Verify file exists and has spans (check for both formats)
        ndjson_files = list(self.trace_dir.glob("*.ndjson"))
        json_files = list(self.trace_dir.glob("trace_*.json"))
        assert len(ndjson_files) == 1 or len(json_files) == 1

        trace = self._read_trace_file()
        assert trace is not None
        assert trace["span_count"] == 2

        # Verify error span has correct status
        error_span = None
        for span in trace["spans"]:
            if span["status"] == "error":
                error_span = span
                break

        assert error_span is not None
        assert "Startup failed" in error_span["error_message"]

    def test_multiple_spans_with_mixed_status(self) -> None:
        """Verify trace captures both success and error spans."""
        tracer = SemanticTracer(
            service_name="test-mixed",
            output_dir=self.trace_dir,
            enabled=True,
        )
        tracer.start_trace("test-mixed-status")

        # Success span
        with tracer.tool_call("success_tool", {"x": 1}) as span:
            tracer.record_tool_result(span, {"result": "ok"}, success=True)

        # Error span
        with pytest.raises(RuntimeError):
            with tracer.tool_call("error_tool", {"x": 2}):
                raise RuntimeError("Tool failed")

        # Another success span
        with tracer.llm_message("assistant", "Final response", "gpt-4"):
            pass

        # Verify (check for both formats)
        ndjson_files = list(self.trace_dir.glob("*.ndjson"))
        json_files = list(self.trace_dir.glob("trace_*.json"))
        assert len(ndjson_files) == 1 or len(json_files) == 1

        trace = self._read_trace_file()
        assert trace is not None
        assert trace["span_count"] == 3

        statuses = [s["status"] for s in trace["spans"]]
        assert statuses.count("ok") == 2
        assert statuses.count("error") == 1
