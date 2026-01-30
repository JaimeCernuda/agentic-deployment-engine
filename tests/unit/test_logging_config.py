"""Comprehensive tests for src/logging_config.py module.

Tests logging configuration including:
- JSON formatter
- Console formatter with colors
- setup_logging function
- Logger adapter with correlation ID
- Edge cases and error handling
"""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_formats_basic_record(self) -> None:
        """Should format log record as JSON."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["line"] == 42
        assert "timestamp" in data

    def test_formats_message_with_args(self) -> None:
        """Should format message with arguments."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Value is %d",
            args=(42,),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["message"] == "Value is 42"

    def test_includes_exception_info(self) -> None:
        """Should include exception info when present."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test error" in data["exception"]

    def test_includes_extra_fields(self) -> None:
        """Should include extra fields if present."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"user_id": 123, "request_id": "abc"}

        result = formatter.format(record)
        data = json.loads(result)

        assert data["extra"]["user_id"] == 123
        assert data["extra"]["request_id"] == "abc"

    def test_includes_correlation_id(self) -> None:
        """Should include correlation ID when present."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "corr-12345"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["correlation_id"] == "corr-12345"

    def test_handles_non_serializable_objects(self) -> None:
        """Should handle non-JSON-serializable objects."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Object: %s",
            args=(object(),),  # Not JSON serializable
            exc_info=None,
        )

        # Should not raise
        result = formatter.format(record)
        data = json.loads(result)
        assert "Object:" in data["message"]


class TestConsoleFormatter:
    """Tests for ConsoleFormatter class."""

    def test_formats_basic_record(self) -> None:
        """Should format log record for console."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        assert "Test message" in result

    def test_adds_colors_in_tty(self) -> None:
        """Should add ANSI colors when in TTY."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        # Mock TTY
        with patch.object(sys.stderr, "isatty", return_value=True):
            result = formatter.format(record)
            # Should contain ANSI color codes
            assert "\033[" in result

    def test_no_colors_in_non_tty(self) -> None:
        """Should not add colors when not in TTY."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        # Mock non-TTY
        with patch.object(sys.stderr, "isatty", return_value=False):
            result = formatter.format(record)
            # Should not contain ANSI color codes
            assert "\033[" not in result


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up logging handlers after each test."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)

    def test_sets_log_level(self) -> None:
        """Should set the specified log level."""
        from src.observability.logging import setup_logging

        with patch.dict(os.environ, {}, clear=True):
            setup_logging(level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_reads_level_from_environment(self) -> None:
        """Should read log level from LOG_LEVEL env var."""
        from src.observability.logging import setup_logging

        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}):
            setup_logging(level="DEBUG")  # Should be overridden

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_uses_json_format_from_env(self) -> None:
        """Should enable JSON format from LOG_JSON env var."""
        from src.observability.logging import JSONFormatter, setup_logging

        with patch.dict(os.environ, {"LOG_JSON": "true"}, clear=True):
            setup_logging()

        root_logger = logging.getLogger()
        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler.formatter, JSONFormatter)

    def test_creates_file_handler(self, tmp_path: Path) -> None:
        """Should create file handler when log_file specified."""
        from src.observability.logging import setup_logging

        log_file = tmp_path / "test.log"

        with patch.dict(os.environ, {}, clear=True):
            setup_logging(log_file=log_file)

        root_logger = logging.getLogger()
        file_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Should create parent directory for log file."""
        from src.observability.logging import setup_logging

        log_file = tmp_path / "subdir" / "nested" / "test.log"

        with patch.dict(os.environ, {}, clear=True):
            setup_logging(log_file=log_file)

        assert log_file.parent.exists()

    def test_reduces_third_party_noise(self) -> None:
        """Should reduce logging level for noisy libraries."""
        from src.observability.logging import setup_logging

        with patch.dict(os.environ, {}, clear=True):
            setup_logging(level="DEBUG")

        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level >= logging.WARNING

        uvicorn_logger = logging.getLogger("uvicorn.access")
        assert uvicorn_logger.level >= logging.WARNING

    def test_clears_existing_handlers(self) -> None:
        """Should clear existing handlers before setup."""
        from src.observability.logging import setup_logging

        root_logger = logging.getLogger()
        root_logger.addHandler(logging.StreamHandler())
        root_logger.addHandler(logging.StreamHandler())
        initial_count = len(root_logger.handlers)

        with patch.dict(os.environ, {}, clear=True):
            setup_logging()

        # Should have exactly 1 handler (console)
        assert len(root_logger.handlers) == 1
        assert len(root_logger.handlers) < initial_count


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_with_name(self) -> None:
        """Should return logger with specified name."""
        from src.observability.logging import get_logger

        logger = get_logger("my.module")
        assert logger.name == "my.module"

    def test_returns_same_logger_for_same_name(self) -> None:
        """Should return same logger instance for same name."""
        from src.observability.logging import get_logger

        logger1 = get_logger("test.logger")
        logger2 = get_logger("test.logger")
        assert logger1 is logger2


class TestLoggerAdapter:
    """Tests for LoggerAdapter class."""

    def test_init_with_correlation_id(self) -> None:
        """Should initialize with correlation ID."""
        from src.observability.logging import LoggerAdapter

        base_logger = logging.getLogger("test")
        adapter = LoggerAdapter(base_logger, "corr-123")

        assert adapter.extra["correlation_id"] == "corr-123"

    def test_adds_correlation_id_to_logs(self) -> None:
        """Should add correlation ID to log records."""
        from src.observability.logging import LoggerAdapter

        base_logger = logging.getLogger("test.adapter")
        adapter = LoggerAdapter(base_logger, "corr-456")

        msg, kwargs = adapter.process("Test message", {})

        assert kwargs["extra"]["correlation_id"] == "corr-456"

    def test_preserves_existing_extra(self) -> None:
        """Should preserve existing extra fields."""
        from src.observability.logging import LoggerAdapter

        base_logger = logging.getLogger("test.adapter")
        adapter = LoggerAdapter(base_logger, "corr-789")

        msg, kwargs = adapter.process("Test", {"extra": {"user_id": 123}})

        assert kwargs["extra"]["correlation_id"] == "corr-789"
        assert kwargs["extra"]["user_id"] == 123


class TestConsoleFormatterColors:
    """Tests for color codes in ConsoleFormatter."""

    def test_debug_color_cyan(self) -> None:
        """DEBUG level should use cyan color."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s")
        assert formatter.COLORS["DEBUG"] == "\033[36m"

    def test_info_color_green(self) -> None:
        """INFO level should use green color."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s")
        assert formatter.COLORS["INFO"] == "\033[32m"

    def test_warning_color_yellow(self) -> None:
        """WARNING level should use yellow color."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s")
        assert formatter.COLORS["WARNING"] == "\033[33m"

    def test_error_color_red(self) -> None:
        """ERROR level should use red color."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s")
        assert formatter.COLORS["ERROR"] == "\033[31m"

    def test_critical_color_magenta(self) -> None:
        """CRITICAL level should use magenta color."""
        from src.observability.logging import ConsoleFormatter

        formatter = ConsoleFormatter(fmt="%(levelname)s")
        assert formatter.COLORS["CRITICAL"] == "\033[35m"


class TestJSONFormatterTimestamp:
    """Tests for timestamp handling in JSONFormatter."""

    def test_timestamp_is_iso_format(self) -> None:
        """Timestamp should be in ISO 8601 format."""
        from src.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        # ISO format has 'T' separator and timezone info
        assert "T" in data["timestamp"]
        # Should end with timezone (Z or +00:00)
        assert data["timestamp"].endswith("+00:00") or data["timestamp"].endswith("Z")


class TestSetupLoggingEdgeCases:
    """Tests for edge cases in setup_logging."""

    def teardown_method(self) -> None:
        """Clean up logging handlers."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

    def test_invalid_log_level_defaults_to_info(self) -> None:
        """Should default to INFO for invalid log level."""
        from src.observability.logging import setup_logging

        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_json_format_parameter(self) -> None:
        """Should use JSON format when parameter is True."""
        from src.observability.logging import JSONFormatter, setup_logging

        with patch.dict(os.environ, {}, clear=True):
            setup_logging(json_format=True)

        root_logger = logging.getLogger()
        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler.formatter, JSONFormatter)

    def test_log_json_env_values(self) -> None:
        """Should recognize various truthy values for LOG_JSON."""
        from src.observability.logging import JSONFormatter, setup_logging

        for value in ["true", "1", "yes", "TRUE", "YES"]:
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            with patch.dict(os.environ, {"LOG_JSON": value}, clear=True):
                setup_logging()

            console_handler = root_logger.handlers[0]
            assert isinstance(console_handler.formatter, JSONFormatter), (
                f"Failed for {value}"
            )
