"""Tests for telemetry module in src/observability/telemetry.py.

Tests cover:
- setup_telemetry function
- instrument_fastapi function
- Context injection/extraction
- traced_operation context manager
- Span attribute recording
- Exception recording
- Shutdown
"""

from unittest.mock import MagicMock

from src.observability import telemetry


class TestSetupTelemetry:
    """Test setup_telemetry function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_disabled_returns_none(self) -> None:
        """When disabled, returns None immediately."""
        result = telemetry.setup_telemetry(enabled=False)
        assert result is None

    def test_idempotent_returns_same_tracer(self) -> None:
        """Multiple calls return the same tracer when already initialized."""
        mock_tracer = MagicMock()
        telemetry._initialized = True
        telemetry._tracer = mock_tracer

        result = telemetry.setup_telemetry(enabled=True)

        # Returns cached tracer when already initialized
        assert result == mock_tracer


class TestGetTracer:
    """Test get_tracer function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_returns_none_when_not_initialized(self) -> None:
        """Returns None when telemetry not initialized."""
        telemetry._tracer = None

        result = telemetry.get_tracer()

        assert result is None

    def test_returns_tracer_when_initialized(self) -> None:
        """Returns tracer when initialized."""
        mock_tracer = MagicMock()
        telemetry._tracer = mock_tracer

        result = telemetry.get_tracer()

        assert result == mock_tracer


class TestInjectContext:
    """Test inject_context function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_returns_headers_unchanged_when_disabled(self) -> None:
        """Returns headers unchanged when telemetry is disabled."""
        telemetry._initialized = False

        headers = {"Content-Type": "application/json"}
        result = telemetry.inject_context(headers)

        assert result == headers

    def test_returns_headers_when_enabled(self) -> None:
        """Returns headers when telemetry is enabled."""
        telemetry._initialized = True

        headers = {"Content-Type": "application/json"}
        result = telemetry.inject_context(headers)

        # Should return headers (may have additional trace headers)
        assert "Content-Type" in result


class TestExtractContext:
    """Test extract_context function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_returns_none_when_disabled(self) -> None:
        """Returns None when telemetry is disabled."""
        telemetry._initialized = False

        result = telemetry.extract_context({"traceparent": "00-..."})

        assert result is None

    def test_returns_value_when_enabled(self) -> None:
        """Returns value when telemetry is enabled."""
        telemetry._initialized = True

        telemetry.extract_context({"traceparent": "00-..."})

        # May return None or context depending on OTel being installed
        # Just verify it doesn't crash


class TestTracedOperation:
    """Test traced_operation context manager."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_yields_none_when_no_tracer(self) -> None:
        """Yields None when tracer is not configured."""
        telemetry._tracer = None

        with telemetry.traced_operation("test_op") as span:
            assert span is None

    def test_creates_span_when_tracer_configured(self) -> None:
        """Creates span when tracer is configured."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=None
        )

        telemetry._tracer = mock_tracer

        with telemetry.traced_operation("test_op") as span:
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_once_with("test_op")

    def test_sets_attributes_on_span(self) -> None:
        """Sets attributes on span when provided."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=None
        )

        telemetry._tracer = mock_tracer

        with telemetry.traced_operation("test_op", {"key": "value"}):
            pass

        mock_span.set_attribute.assert_called_with("key", "value")


class TestAddSpanAttribute:
    """Test add_span_attribute function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_noop_when_disabled(self) -> None:
        """Does nothing when telemetry is disabled."""
        telemetry._initialized = False

        # Should not raise
        telemetry.add_span_attribute("key", "value")

    def test_noop_when_enabled_but_no_errors(self) -> None:
        """Does nothing visible when enabled but no span."""
        telemetry._initialized = True

        # Should not raise even without active span
        telemetry.add_span_attribute("key", "value")


class TestRecordException:
    """Test record_exception function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_noop_when_disabled(self) -> None:
        """Does nothing when telemetry is disabled."""
        telemetry._initialized = False

        # Should not raise
        telemetry.record_exception(ValueError("test"))

    def test_noop_when_enabled_no_active_span(self) -> None:
        """Does nothing when enabled but no active span."""
        telemetry._initialized = True

        # Should not raise even without active span
        telemetry.record_exception(ValueError("test"))


class TestShutdownTelemetry:
    """Test shutdown_telemetry function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_noop_when_not_initialized(self) -> None:
        """Does nothing when not initialized."""
        telemetry._initialized = False

        # Should not raise
        telemetry.shutdown_telemetry()

    def test_resets_state_when_initialized(self) -> None:
        """Resets module state when initialized."""
        telemetry._initialized = True
        telemetry._tracer = MagicMock()

        telemetry.shutdown_telemetry()

        assert telemetry._initialized is False
        assert telemetry._tracer is None


class TestInstrumentFastAPI:
    """Test instrument_fastapi function."""

    def teardown_method(self) -> None:
        """Reset telemetry state after each test."""
        telemetry._initialized = False
        telemetry._tracer = None

    def test_noop_when_not_initialized(self) -> None:
        """Does nothing when telemetry not initialized."""
        telemetry._initialized = False

        mock_app = MagicMock()

        # Should not raise
        telemetry.instrument_fastapi(mock_app)

    def test_noop_when_initialized_but_instrumentor_missing(self) -> None:
        """Does nothing when instrumentor not available."""
        telemetry._initialized = True

        mock_app = MagicMock()

        # Should not raise even if instrumentor not installed
        telemetry.instrument_fastapi(mock_app)
