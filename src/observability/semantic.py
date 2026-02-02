"""Semantic observability for deep workflow introspection.

Provides rich semantic tracing at three levels:
1. Framework level - Job deployment, agent lifecycle
2. A2A level - Message exchange, context propagation, sessions
3. Agent level - Tool calls, LLM messages, inputs/outputs

Traces can be exported to JSON files for analysis without external collectors.

Usage:
    from src.observability.semantic import SemanticTracer

    tracer = SemanticTracer(service_name="my-agent", output_dir="traces/")

    # Framework level
    with tracer.job_deployment("my-job", agents=["weather", "maps"]):
        deploy_agents()

    # A2A level
    with tracer.a2a_message(
        source="controller",
        target="weather",
        query="What's the weather?",
        context_id="session-123"
    ):
        response = await query_agent()

    # Agent level
    with tracer.tool_call("get_weather", {"city": "Tokyo"}):
        result = get_weather("Tokyo")
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Windows compatibility for file locking
if sys.platform == "win32":
    import msvcrt

    def _lock_file(f) -> None:
        """Lock file for exclusive write access (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(f) -> None:
        """Unlock file (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(f) -> None:
        """Lock file for exclusive write access (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock_file(f) -> None:
        """Unlock file (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# Context variable to propagate agent name through spans
# This allows SDK hooks and A2A transport to know which agent they're tracing
_current_agent_name: ContextVar[str | None] = ContextVar("agent_name", default=None)


@dataclass
class SpanData:
    """Semantic span data structure."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    level: str  # "framework", "a2a", "agent"
    category: str  # More specific category within level
    start_time: str
    end_time: str | None = None
    duration_ms: float | None = None
    status: str = "ok"  # "ok", "error"
    error_message: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


class JSONFileExporter:
    """Export traces to JSON files for offline analysis."""

    def __init__(self, output_dir: Path | str):
        """Initialize file exporter.

        Args:
            output_dir: Directory to write trace files.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_file: Path | None = None
        self._spans: list[SpanData] = []

    def start_trace(self, trace_id: str, name: str) -> None:
        """Start a new trace file.

        Args:
            trace_id: Unique trace identifier.
            name: Human-readable trace name.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        self._current_file = self.output_dir / f"trace_{timestamp}_{safe_name}.json"
        self._spans = []

    def export_span(self, span: SpanData) -> None:
        """Export a span to the current trace file.

        Args:
            span: Span data to export.
        """
        with self._lock:
            self._spans.append(span)
            self._write_file()

    def _write_file(self) -> None:
        """Write current spans to file."""
        if not self._current_file:
            return

        trace_data = {
            "export_time": datetime.now(UTC).isoformat(),
            "span_count": len(self._spans),
            "spans": [asdict(s) for s in self._spans],
        }

        with open(self._current_file, "w") as f:
            json.dump(trace_data, f, indent=2, default=str)

    def get_output_path(self) -> Path | None:
        """Get the current trace file path."""
        return self._current_file


class SharedNDJSONExporter:
    """Export traces to shared NDJSON files for live cross-agent tracing.

    This exporter writes spans to NDJSON (newline-delimited JSON) files,
    using the trace_id as the filename. Multiple agents can safely write
    to the same file using file locking, enabling true distributed tracing
    without requiring an external trace collector.

    Unlike JSONFileExporter which creates a new file per agent, this exporter
    ensures all spans with the same trace_id end up in the same file DURING
    execution, not via post-hoc merge.
    """

    def __init__(self, output_dir: Path | str):
        """Initialize shared NDJSON exporter.

        Args:
            output_dir: Directory to write trace files.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_trace_id: str | None = None
        self._current_file: Path | None = None

    def start_trace(self, trace_id: str, name: str) -> None:
        """Start a new trace or continue an existing one.

        Uses trace_id as the filename, so all agents with the same
        trace_id write to the same file.

        Args:
            trace_id: Unique trace identifier (used as filename).
            name: Human-readable trace name (stored in metadata).
        """
        with self._lock:
            self._current_trace_id = trace_id
            # Use trace_id as filename (sanitized)
            safe_trace_id = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in trace_id
            )
            self._current_file = self.output_dir / f"{safe_trace_id}.ndjson"

            # Write metadata line if this is a new file
            if not self._current_file.exists():
                metadata = {
                    "_type": "trace_metadata",
                    "trace_id": trace_id,
                    "trace_name": name,
                    "started_at": datetime.now(UTC).isoformat(),
                }
                self._append_line(metadata)

    def continue_trace(self, trace_id: str) -> None:
        """Continue an existing trace from another agent.

        Opens the existing trace file for appending without writing
        new metadata.

        Args:
            trace_id: The parent trace ID to continue.
        """
        with self._lock:
            self._current_trace_id = trace_id
            safe_trace_id = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in trace_id
            )
            self._current_file = self.output_dir / f"{safe_trace_id}.ndjson"
            # Don't write metadata - just set up for appending

    def export_span(self, span: SpanData) -> None:
        """Export a span to the shared trace file.

        Uses file locking for safe concurrent writes from multiple agents.

        Args:
            span: Span data to export.
        """
        if not self._current_file:
            return

        span_dict = asdict(span)
        span_dict["_type"] = "span"
        self._append_line(span_dict)

    def _append_line(self, data: dict[str, Any]) -> None:
        """Append a single JSON line to the trace file with locking.

        Args:
            data: Dictionary to serialize as JSON line.
        """
        if not self._current_file:
            return

        line = json.dumps(data, default=str) + "\n"

        # Use file locking for safe multi-process writes
        with open(self._current_file, "a", encoding="utf-8") as f:
            try:
                _lock_file(f)
                f.write(line)
                f.flush()
            finally:
                try:
                    _unlock_file(f)
                except Exception:
                    pass  # Best effort unlock

    def get_output_path(self) -> Path | None:
        """Get the current trace file path."""
        return self._current_file


def read_ndjson_trace(trace_file: Path | str) -> dict[str, Any] | None:
    """Read an NDJSON trace file into a unified trace structure.

    Converts the NDJSON format back to the standard trace JSON format
    for compatibility with existing analysis tools.

    Args:
        trace_file: Path to the NDJSON trace file.

    Returns:
        Unified trace dict, or None if file doesn't exist.
    """
    trace_path = Path(trace_file)
    if not trace_path.exists():
        return None

    metadata: dict[str, Any] = {}
    spans: list[dict[str, Any]] = []
    agent_names: set[str] = set()
    trace_ids: set[str] = set()

    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                entry_type = data.pop("_type", "span")

                if entry_type == "trace_metadata":
                    metadata = data
                elif entry_type == "span":
                    spans.append(data)
                    trace_ids.add(data.get("trace_id", "unknown"))
                    agent_name = data.get("attributes", {}).get("agent.name")
                    if agent_name:
                        agent_names.add(agent_name)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON line in trace file: {line[:100]}")

    # Sort spans by start_time
    spans.sort(key=lambda s: s.get("start_time", ""))

    return {
        "trace_file": str(trace_path),
        "export_time": datetime.now(UTC).isoformat(),
        "trace_id": metadata.get("trace_id"),
        "trace_name": metadata.get("trace_name"),
        "started_at": metadata.get("started_at"),
        "span_count": len(spans),
        "trace_ids": list(trace_ids),
        "agents": list(agent_names),
        "spans": spans,
    }


class SpanContext:
    """Thread-local span context for parent tracking."""

    _local = threading.local()

    @classmethod
    def get_current(cls) -> SpanData | None:
        """Get the current span."""
        return getattr(cls._local, "current_span", None)

    @classmethod
    def set_current(cls, span: SpanData | None) -> None:
        """Set the current span."""
        cls._local.current_span = span


class SemanticTracer:
    """Semantic tracer for deep workflow observability.

    Provides structured tracing at framework, A2A, and agent levels
    with rich semantic attributes for debugging and analysis.

    Supports live cross-agent trace propagation via SharedNDJSONExporter,
    which writes all spans with the same trace_id to a single file during
    execution. This enables true distributed tracing without requiring
    an external trace collector.

    Trace ID Propagation:
    1. Job-level: Deployer sets AGENT_JOB_TRACE_ID for all agents
    2. Request-level: X-Semantic-Trace-Id header propagates trace context
    3. Auto-continuation: If parent trace_id is detected, spans append to same file
    """

    def __init__(
        self,
        service_name: str = "agentic-deployment",
        output_dir: str | Path | None = None,
        enabled: bool = True,
        use_shared_exporter: bool = True,
    ):
        """Initialize semantic tracer.

        Args:
            service_name: Name of the service being traced.
            output_dir: Directory for trace files. None disables file export.
            enabled: Whether tracing is enabled.
            use_shared_exporter: Use SharedNDJSONExporter (True) for live
                cross-agent tracing, or JSONFileExporter (False) for legacy mode.
        """
        self.service_name = service_name
        self.enabled = enabled
        self._trace_id: str | None = None
        self._use_shared_exporter = use_shared_exporter

        # File exporter - prefer SharedNDJSONExporter for live cross-agent tracing
        if output_dir and enabled:
            if use_shared_exporter:
                self.exporter = SharedNDJSONExporter(output_dir)
            else:
                self.exporter = JSONFileExporter(output_dir)
        else:
            self.exporter = None

        # Check for job-level trace_id from deployer
        # This enables all agents in a job to share the same trace file
        job_trace_id = os.environ.get("AGENT_JOB_TRACE_ID")
        if job_trace_id and enabled and self.exporter:
            self._trace_id = job_trace_id
            # Continue the existing trace (don't write new metadata)
            if isinstance(self.exporter, SharedNDJSONExporter):
                self.exporter.continue_trace(job_trace_id)
            else:
                self.exporter.start_trace(job_trace_id, f"agent-{service_name}")
            logger.debug(f"Continuing job trace: {job_trace_id}")

        # Also use OTEL if available
        self._otel_tracer = None
        if enabled:
            try:
                from opentelemetry import trace

                self._otel_tracer = trace.get_tracer(__name__)
            except ImportError:
                pass

    def start_trace(self, name: str, parent_trace_id: str | None = None) -> str:
        """Start a new trace or continue an existing one.

        For SharedNDJSONExporter: If parent_trace_id is provided, appends to
        the existing trace file rather than creating a new one.

        Args:
            name: Human-readable trace name.
            parent_trace_id: Optional parent trace ID for cross-agent correlation.
                             If provided, this trace will be linked to the parent.

        Returns:
            Trace ID.
        """
        # Use parent trace_id if provided (for cross-agent correlation)
        self._trace_id = parent_trace_id or str(uuid.uuid4())
        if self.exporter:
            if parent_trace_id and isinstance(self.exporter, SharedNDJSONExporter):
                # Continue existing trace - don't write new metadata
                self.exporter.continue_trace(self._trace_id)
            else:
                # Start new trace - write metadata
                self.exporter.start_trace(self._trace_id, name)
        return self._trace_id

    def get_trace_id(self) -> str | None:
        """Get the current trace ID.

        Returns:
            Current trace ID or None if no trace is active.
        """
        return self._trace_id

    def continue_trace(self, trace_id: str) -> None:
        """Continue an existing trace from another agent.

        Use this to correlate traces across A2A calls. With SharedNDJSONExporter,
        this also opens the shared trace file for appending.

        Args:
            trace_id: The parent trace ID to continue.
        """
        self._trace_id = trace_id
        if self.exporter and isinstance(self.exporter, SharedNDJSONExporter):
            self.exporter.continue_trace(trace_id)

    def _create_span(
        self,
        name: str,
        level: str,
        category: str,
        attributes: dict[str, Any] | None = None,
    ) -> SpanData:
        """Create a new span.

        Args:
            name: Span name.
            level: Observability level (framework, a2a, agent).
            category: Specific category within level.
            attributes: Initial attributes.

        Returns:
            New span data.
        """
        parent = SpanContext.get_current()

        # Build base attributes
        span_attrs = {
            "service.name": self.service_name,
            **(attributes or {}),
        }

        # Add agent name from context if available and not already set
        agent_name = _current_agent_name.get()
        if agent_name and "agent.name" not in span_attrs:
            span_attrs["agent.name"] = agent_name

        # Ensure consistent trace_id across all spans in the same request
        if self._trace_id is None:
            self._trace_id = str(uuid.uuid4())
            # Also initialize the exporter's trace file
            if self.exporter:
                self.exporter.start_trace(
                    self._trace_id, f"agent-query-{self._trace_id[:8]}"
                )

        return SpanData(
            trace_id=self._trace_id,
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent.span_id if parent else None,
            name=name,
            level=level,
            category=category,
            start_time=datetime.now(UTC).isoformat(),
            attributes=span_attrs,
        )

    def _finish_span(
        self,
        span: SpanData,
        error: Exception | None = None,
    ) -> None:
        """Finish and export a span.

        Args:
            span: Span to finish.
            error: Optional exception if span errored.
        """
        end_time = datetime.now(UTC)
        span.end_time = end_time.isoformat()

        # Calculate duration
        start = datetime.fromisoformat(span.start_time)
        span.duration_ms = (end_time - start).total_seconds() * 1000

        if error:
            span.status = "error"
            span.error_message = str(error)

        if self.exporter:
            self.exporter.export_span(span)

    @contextmanager
    def _span_context(
        self,
        name: str,
        level: str,
        category: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[SpanData, None, None]:
        """Context manager for span lifecycle.

        Args:
            name: Span name.
            level: Observability level.
            category: Specific category.
            attributes: Span attributes.

        Yields:
            The active span.
        """
        if not self.enabled:
            # Yield a dummy span
            yield SpanData(
                trace_id="disabled",
                span_id="disabled",
                parent_span_id=None,
                name=name,
                level=level,
                category=category,
                start_time=datetime.now(UTC).isoformat(),
            )
            return

        span = self._create_span(name, level, category, attributes)
        previous_span = SpanContext.get_current()
        SpanContext.set_current(span)

        error = None
        try:
            yield span
        except Exception as e:
            error = e
            raise
        finally:
            SpanContext.set_current(previous_span)
            self._finish_span(span, error)

    # =========================================================================
    # Framework Level Spans
    # =========================================================================

    @contextmanager
    def job_deployment(
        self,
        job_id: str,
        job_name: str,
        agents: list[str],
        topology: str | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace job deployment.

        Args:
            job_id: Unique job identifier.
            job_name: Human-readable job name.
            agents: List of agent IDs being deployed.
            topology: Topology type (hub-spoke, pipeline, etc.).

        Yields:
            Active span.
        """
        if not self._trace_id:
            self.start_trace(f"deploy-{job_name}")

        with self._span_context(
            name=f"deploy:{job_name}",
            level="framework",
            category="job_deployment",
            attributes={
                "job.id": job_id,
                "job.name": job_name,
                "job.agent_count": len(agents),
                "job.agents": agents,
                "job.topology": topology,
            },
        ) as span:
            yield span

    @contextmanager
    def agent_lifecycle(
        self,
        agent_id: str,
        agent_name: str,
        action: str,  # "start", "stop", "health_check"
        port: int | None = None,
        host: str | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace agent lifecycle events.

        Args:
            agent_id: Agent identifier.
            agent_name: Human-readable agent name.
            action: Lifecycle action being performed.
            port: Agent port.
            host: Agent host.

        Yields:
            Active span.
        """
        with self._span_context(
            name=f"agent:{action}:{agent_id}",
            level="framework",
            category="agent_lifecycle",
            attributes={
                "agent.id": agent_id,
                "agent.name": agent_name,
                "agent.action": action,
                "agent.port": port,
                "agent.host": host or "localhost",
            },
        ) as span:
            yield span

    # =========================================================================
    # A2A Level Spans
    # =========================================================================

    @contextmanager
    def a2a_message(
        self,
        source_agent: str,
        target_agent: str,
        query: str,
        context_id: str | None = None,
        session_id: str | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace A2A message exchange.

        Args:
            source_agent: Sending agent ID.
            target_agent: Receiving agent ID.
            query: The query being sent.
            context_id: A2A context ID.
            session_id: Session ID for multi-turn.

        Yields:
            Active span.
        """
        with self._span_context(
            name=f"a2a:{source_agent}->{target_agent}",
            level="a2a",
            category="message_exchange",
            attributes={
                "a2a.source": source_agent,
                "a2a.target": target_agent,
                "a2a.query": query[:500] if query else None,  # Truncate for size
                "a2a.query_length": len(query) if query else 0,
                "a2a.context_id": context_id,
                "a2a.session_id": session_id,
            },
        ) as span:
            yield span

    def record_a2a_response(
        self,
        span: SpanData,
        response: str,
        status_code: int = 200,
        tools_used: list[str] | None = None,
    ) -> None:
        """Record A2A response details on a span.

        Args:
            span: The span to update.
            response: Response text.
            status_code: HTTP status code.
            tools_used: Tools used in response.
        """
        span.attributes.update(
            {
                "a2a.response": response[:500] if response else None,
                "a2a.response_length": len(response) if response else 0,
                "a2a.status_code": status_code,
                "a2a.tools_used": tools_used or [],
            }
        )

    @contextmanager
    def agent_discovery(
        self,
        agent_url: str,
        discovered_skills: list[str] | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace agent discovery.

        Args:
            agent_url: URL of agent being discovered.
            discovered_skills: Skills found on the agent.

        Yields:
            Active span.
        """
        with self._span_context(
            name=f"discover:{agent_url}",
            level="a2a",
            category="discovery",
            attributes={
                "discovery.url": agent_url,
                "discovery.skills": discovered_skills,
            },
        ) as span:
            yield span

    @contextmanager
    def registry_discovery(
        self,
        source_agent: str,
        registry_url: str,
        search_params: dict[str, str] | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace registry-based agent discovery.

        Used when an agent searches the dynamic registry for other agents
        by skill, tag, or name.

        Args:
            source_agent: Agent performing the discovery.
            registry_url: URL of the registry service.
            search_params: Search parameters (skill, tag, name, etc.).

        Yields:
            Active span.
        """
        params = search_params or {}
        search_desc = ", ".join(
            f"{k}={v}" for k, v in params.items() if v and k != "healthy_only"
        )
        with self._span_context(
            name=f"registry_discovery:{source_agent}",
            level="a2a",
            category="registry_discovery",
            attributes={
                "registry.url": registry_url,
                "registry.source_agent": source_agent,
                "registry.search_skill": params.get("skill"),
                "registry.search_tag": params.get("tag"),
                "registry.search_name": params.get("name"),
                "registry.search_desc": search_desc or "all agents",
            },
        ) as span:
            yield span

    # =========================================================================
    # Agent Level Spans
    # =========================================================================

    @contextmanager
    def query_handling(
        self,
        agent_name: str,
        query: str,
        session_id: str | None = None,
        history_length: int = 0,
    ) -> Generator[SpanData, None, None]:
        """Trace query handling within an agent.

        Sets agent context so all child spans (tool calls, LLM messages, A2A)
        automatically include the agent.name attribute.

        Args:
            agent_name: Name of the handling agent.
            query: The incoming query.
            session_id: Session ID if multi-turn.
            history_length: Length of conversation history.

        Yields:
            Active span.
        """
        # Set agent context for child spans (SDK hooks, A2A transport, etc.)
        token = _current_agent_name.set(agent_name)
        try:
            with (
                self._span_context(
                    name=f"query:{agent_name}",
                    level="agent",
                    category="query_handling",
                    attributes={
                        "query.agent": agent_name,
                        "agent.name": agent_name,  # Also set explicitly on this span
                        "query.text": query[:500] if query else None,
                        "query.length": len(query) if query else 0,
                        "query.session_id": session_id,
                        "query.history_length": history_length,
                    },
                ) as span
            ):
                yield span
        finally:
            _current_agent_name.reset(token)

    @contextmanager
    def tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | str | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace a tool call.

        Args:
            tool_name: Name of the tool being called.
            tool_input: Input to the tool.

        Yields:
            Active span.
        """
        # Safely serialize input
        if isinstance(tool_input, dict):
            input_str = json.dumps(tool_input, default=str)[:500]
        elif tool_input:
            input_str = str(tool_input)[:500]
        else:
            input_str = None

        with self._span_context(
            name=f"tool:{tool_name}",
            level="agent",
            category="tool_call",
            attributes={
                "tool.name": tool_name,
                "tool.input": input_str,
            },
        ) as span:
            yield span

    def record_tool_result(
        self,
        span: SpanData,
        result: Any,
        success: bool = True,
    ) -> None:
        """Record tool call result on a span.

        Args:
            span: The span to update.
            result: Tool result.
            success: Whether the tool succeeded.
        """
        if isinstance(result, dict):
            result_str = json.dumps(result, default=str)[:500]
        else:
            result_str = str(result)[:500] if result else None

        span.attributes.update(
            {
                "tool.result": result_str,
                "tool.success": success,
            }
        )

    @contextmanager
    def llm_inference(
        self,
        model: str,
        prompt_length: int | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace an LLM inference call (query to full response).

        This captures the total time from sending a query to receiving
        all response messages. Child llm_message spans provide per-message
        detail within this parent span.

        Args:
            model: LLM model being used.
            prompt_length: Length of the prompt in characters.

        Yields:
            Active span.
        """
        with self._span_context(
            name=f"llm:inference:{model}",
            level="agent",
            category="llm_inference",
            attributes={
                "llm.model": model,
                "llm.prompt_length": prompt_length,
            },
        ) as span:
            yield span

    def record_llm_response(
        self,
        span: SpanData,
        response_length: int,
        message_count: int,
        tool_count: int,
        time_to_first_token_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_cost_usd: float | None = None,
    ) -> None:
        """Record LLM response metrics on an inference span.

        Args:
            span: The llm_inference span to update.
            response_length: Total response length in characters.
            message_count: Number of messages received.
            tool_count: Number of tool calls made.
            time_to_first_token_ms: Time to first token in milliseconds.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
            total_cost_usd: Total cost in USD (if available from API).
        """
        span.attributes.update(
            {
                "llm.response_length": response_length,
                "llm.message_count": message_count,
                "llm.tool_count": tool_count,
            }
        )
        if time_to_first_token_ms is not None:
            span.attributes["llm.ttft_ms"] = time_to_first_token_ms
        if input_tokens is not None:
            span.attributes["llm.input_tokens"] = input_tokens
        if output_tokens is not None:
            span.attributes["llm.output_tokens"] = output_tokens
        if total_cost_usd is not None:
            span.attributes["llm.cost_usd"] = total_cost_usd

    @contextmanager
    def llm_message(
        self,
        role: str,  # "user", "assistant", "system"
        content: str,
        model: str | None = None,
    ) -> Generator[SpanData, None, None]:
        """Trace an LLM message.

        Args:
            role: Message role.
            content: Message content.
            model: LLM model being used.

        Yields:
            Active span.
        """
        with self._span_context(
            name=f"llm:{role}",
            level="agent",
            category="llm_message",
            attributes={
                "llm.role": role,
                "llm.content": content[:500] if content else None,
                "llm.content_length": len(content) if content else 0,
                "llm.model": model,
            },
        ) as span:
            yield span

    def add_event(
        self,
        span: SpanData,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to a span.

        Args:
            span: The span to update.
            name: Event name.
            attributes: Event attributes.
        """
        span.events.append(
            {
                "name": name,
                "timestamp": datetime.now(UTC).isoformat(),
                "attributes": attributes or {},
            }
        )

    def get_trace_file(self) -> Path | None:
        """Get the current trace file path."""
        if self.exporter:
            return self.exporter.get_output_path()
        return None


# Global tracer instance (initialized on first use)
_global_tracer: SemanticTracer | None = None


def get_semantic_tracer(
    service_name: str | None = None,
    output_dir: str | Path | None = None,
    force_enabled: bool | None = None,
) -> SemanticTracer:
    """Get or create the global semantic tracer.

    Configuration via environment variables or settings:
        AGENT_SEMANTIC_TRACING_ENABLED: Enable semantic tracing (default: false)
        AGENT_SEMANTIC_TRACE_DIR: Trace output directory (default: traces/)
        AGENT_OTEL_SERVICE_NAME: Service name for traces

    Args:
        service_name: Service name (used only on first call).
        output_dir: Trace output directory (used only on first call).
        force_enabled: Force enable/disable tracing (overrides settings).

    Returns:
        Global tracer instance.
    """
    global _global_tracer

    if _global_tracer is None:
        # Try to get from pydantic settings first, then fall back to env vars
        try:
            from ..config import settings

            enabled = (
                force_enabled
                if force_enabled is not None
                else settings.semantic_tracing_enabled
            )
            output = output_dir or settings.semantic_trace_dir
            svc_name = service_name or settings.otel_service_name

        except (ImportError, AttributeError):
            # Fall back to environment variables
            enabled = (
                force_enabled
                if force_enabled is not None
                else os.getenv(
                    "AGENT_SEMANTIC_TRACING_ENABLED",
                    os.getenv("SEMANTIC_TRACING_ENABLED", "false"),
                ).lower()
                in ("true", "1", "yes")
            )

            output = output_dir or os.getenv(
                "AGENT_SEMANTIC_TRACE_DIR",
                os.getenv("SEMANTIC_TRACE_DIR", "traces/"),
            )

            svc_name = service_name or os.getenv(
                "AGENT_OTEL_SERVICE_NAME",
                os.getenv("OTEL_SERVICE_NAME", "agentic-deployment-engine"),
            )

        _global_tracer = SemanticTracer(
            service_name=svc_name,
            output_dir=output if enabled else None,
            enabled=enabled,
        )

        if enabled:
            logger.info(f"Semantic tracing enabled: {output} (service: {svc_name})")

    return _global_tracer


def reset_semantic_tracer() -> None:
    """Reset the global tracer (for testing purposes)."""
    global _global_tracer
    _global_tracer = None


def get_current_agent_name() -> str | None:
    """Get the current agent name from context.

    This is set by query_handling() and propagated through all child spans.
    Useful for A2A transport to identify the calling agent.

    Returns:
        Agent name if set, None otherwise.
    """
    return _current_agent_name.get()


def merge_job_traces(job_trace_dir: Path | str) -> dict[str, Any] | None:
    """Merge all trace files from a job into a single unified trace.

    Each agent in a job writes its own trace file. This function combines
    them into a single trace for easier analysis.

    Args:
        job_trace_dir: Directory containing trace files for a job.
                       Typically traces/{job-id}/

    Returns:
        Unified trace dict with all spans merged, or None if no traces found.
    """
    trace_dir = Path(job_trace_dir)
    if not trace_dir.exists():
        return None

    # Find all trace JSON files
    trace_files = list(trace_dir.glob("trace_*.json"))
    if not trace_files:
        return None

    all_spans: list[dict[str, Any]] = []
    trace_ids: set[str] = set()
    agent_names: set[str] = set()

    for trace_file in trace_files:
        try:
            with open(trace_file) as f:
                trace_data = json.load(f)

            spans = trace_data.get("spans", [])
            for span in spans:
                all_spans.append(span)
                trace_ids.add(span.get("trace_id", "unknown"))
                agent_name = span.get("attributes", {}).get("agent.name")
                if agent_name:
                    agent_names.add(agent_name)

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read trace file {trace_file}: {e}")

    if not all_spans:
        return None

    # Sort spans by start_time for chronological order
    all_spans.sort(key=lambda s: s.get("start_time", ""))

    return {
        "job_dir": str(trace_dir),
        "export_time": datetime.now(UTC).isoformat(),
        "source_files": len(trace_files),
        "span_count": len(all_spans),
        "trace_ids": list(trace_ids),
        "agents": list(agent_names),
        "spans": all_spans,
    }


def write_unified_trace(job_trace_dir: Path | str) -> Path | None:
    """Merge job traces and write to a unified trace file.

    Args:
        job_trace_dir: Directory containing trace files for a job.

    Returns:
        Path to unified trace file, or None if no traces found.
    """
    trace_dir = Path(job_trace_dir)
    unified = merge_job_traces(trace_dir)

    if not unified:
        return None

    # Write unified trace
    output_file = trace_dir / "unified_trace.json"
    with open(output_file, "w") as f:
        json.dump(unified, f, indent=2, default=str)

    logger.info(
        f"Unified trace written: {output_file} "
        f"({unified['span_count']} spans from {unified['source_files']} files)"
    )

    return output_file
