"""Centralized logging configuration for the agentic deployment engine.

Provides consistent structured logging across all modules with support for
both human-readable console output and machine-parseable JSON format.
"""

import json
import logging
import os
import sys
from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging.

    Produces newline-delimited JSON logs suitable for log aggregation
    systems like ELK, Splunk, or CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON string with log data.
        """
        log_record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        extra = getattr(record, "extra", None)
        if extra:
            log_record["extra"] = extra

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add correlation ID if available (for distributed tracing)
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id is not None:
            log_record["correlation_id"] = correlation_id

        return json.dumps(log_record, default=str)


class ConsoleFormatter(logging.Formatter):
    """Colored console formatter for human-readable output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console.

        Args:
            record: Log record to format.

        Returns:
            Formatted string with ANSI colors.
        """
        # Add color if terminal supports it
        if sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, "")
            reset = self.RESET
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Path | None = None,
    service_name: str = "agentic-deployment",
) -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, use JSON format for console output.
        log_file: Optional path to log file.
        service_name: Service name for log identification.
    """
    # Get log level from environment or argument
    level = os.getenv("LOG_LEVEL", level).upper()
    log_level = getattr(logging, level, logging.INFO)

    # Check for JSON format from environment
    if os.getenv("LOG_JSON", "").lower() in ("true", "1", "yes"):
        json_format = True

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            ConsoleFormatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds correlation ID to all log records.

    Use this to track requests across distributed services.
    """

    def __init__(self, logger: logging.Logger, correlation_id: str):
        """Initialize adapter with correlation ID.

        Args:
            logger: Base logger instance.
            correlation_id: Unique ID for request correlation.
        """
        super().__init__(logger, {"correlation_id": correlation_id})

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """Add correlation ID to log record.

        Args:
            msg: Log message.
            kwargs: Keyword arguments.

        Returns:
            Processed message and kwargs.
        """
        extra = kwargs.get("extra", {})
        if self.extra is not None:
            extra["correlation_id"] = self.extra.get("correlation_id")
        kwargs["extra"] = extra
        return msg, kwargs
