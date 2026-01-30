"""Tests for custom exceptions in src/core/exceptions.py.

Tests cover:
- AgentError base class
- All specific exception types
- to_dict serialization
- String representation
"""

import pytest

from src.core.exceptions import (
    AgentBackendError,
    AgentError,
    ConfigurationError,
    ConnectionError,
    DeploymentError,
    DiscoveryError,
    SecurityError,
    TimeoutError,
    ValidationError,
)


class TestAgentError:
    """Test AgentError base class."""

    def test_init_with_defaults(self) -> None:
        """AgentError stores message, code, and defaults to recoverable."""
        error = AgentError("Test message", "TEST_CODE")
        assert error.message == "Test message"
        assert error.code == "TEST_CODE"
        assert error.recoverable is True

    def test_init_non_recoverable(self) -> None:
        """AgentError can be marked as non-recoverable."""
        error = AgentError("Critical error", "CRITICAL", recoverable=False)
        assert error.recoverable is False

    def test_str_representation(self) -> None:
        """__str__ includes code and message."""
        error = AgentError("Something went wrong", "ERR_001")
        assert str(error) == "[ERR_001] Something went wrong"

    def test_to_dict(self) -> None:
        """to_dict returns serializable dictionary."""
        error = AgentError("Test message", "TEST_CODE", recoverable=True)
        result = error.to_dict()

        assert result == {
            "error": "TEST_CODE",
            "message": "Test message",
            "recoverable": True,
        }

    def test_is_exception(self) -> None:
        """AgentError is an Exception subclass."""
        error = AgentError("Test", "TEST")
        assert isinstance(error, Exception)


class TestConnectionError:
    """Test ConnectionError exception."""

    def test_init_without_cause(self) -> None:
        """ConnectionError with just URL."""
        error = ConnectionError("http://localhost:9001")
        assert error.url == "http://localhost:9001"
        assert error.cause is None
        assert error.code == "CONN_FAILED"
        assert error.recoverable is True
        assert "http://localhost:9001" in str(error)

    def test_init_with_cause(self) -> None:
        """ConnectionError with cause exception."""
        cause = OSError("Connection refused")
        error = ConnectionError("http://localhost:9001", cause=cause)

        assert error.cause == cause
        assert "Connection refused" in str(error)

    def test_is_agent_error(self) -> None:
        """ConnectionError is an AgentError subclass."""
        error = ConnectionError("http://test")
        assert isinstance(error, AgentError)


class TestTimeoutError:
    """Test TimeoutError exception."""

    def test_init(self) -> None:
        """TimeoutError stores URL and timeout."""
        error = TimeoutError("http://localhost:9001", 30.0)

        assert error.url == "http://localhost:9001"
        assert error.timeout == 30.0
        assert error.code == "TIMEOUT"
        assert error.recoverable is True
        assert "30" in str(error)
        assert "http://localhost:9001" in str(error)

    def test_is_agent_error(self) -> None:
        """TimeoutError is an AgentError subclass."""
        error = TimeoutError("http://test", 10.0)
        assert isinstance(error, AgentError)


class TestSecurityError:
    """Test SecurityError exception."""

    def test_init(self) -> None:
        """SecurityError is not recoverable."""
        error = SecurityError("SSRF attempt blocked")

        assert error.code == "SECURITY"
        assert error.recoverable is False
        assert "SSRF" in str(error)

    def test_is_agent_error(self) -> None:
        """SecurityError is an AgentError subclass."""
        error = SecurityError("Test")
        assert isinstance(error, AgentError)


class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_init(self) -> None:
        """ConfigurationError is not recoverable."""
        error = ConfigurationError("Missing API key")

        assert error.code == "CONFIG"
        assert error.recoverable is False
        assert "API key" in str(error)

    def test_is_agent_error(self) -> None:
        """ConfigurationError is an AgentError subclass."""
        error = ConfigurationError("Test")
        assert isinstance(error, AgentError)


class TestAgentBackendError:
    """Test AgentBackendError exception."""

    def test_init_without_cause(self) -> None:
        """AgentBackendError with backend name and message."""
        error = AgentBackendError("claude", "API rate limit exceeded")

        assert error.backend == "claude"
        assert error.cause is None
        assert error.code == "BACKEND_ERROR"
        assert error.recoverable is True
        assert "[claude]" in str(error)
        assert "rate limit" in str(error)

    def test_init_with_cause(self) -> None:
        """AgentBackendError with cause exception."""
        cause = RuntimeError("Internal error")
        error = AgentBackendError("crewai", "Task failed", cause=cause)

        assert error.cause == cause
        assert "Internal error" in str(error)

    def test_is_agent_error(self) -> None:
        """AgentBackendError is an AgentError subclass."""
        error = AgentBackendError("test", "msg")
        assert isinstance(error, AgentError)


class TestDeploymentError:
    """Test DeploymentError exception."""

    def test_init_without_cause(self) -> None:
        """DeploymentError with target and message."""
        error = DeploymentError("ssh://host", "SSH connection failed")

        assert error.target == "ssh://host"
        assert error.cause is None
        assert error.code == "DEPLOY_ERROR"
        assert error.recoverable is True
        assert "ssh://host" in str(error)
        assert "SSH connection" in str(error)

    def test_init_with_cause(self) -> None:
        """DeploymentError with cause exception."""
        cause = PermissionError("Access denied")
        error = DeploymentError("docker", "Container start failed", cause=cause)

        assert error.cause == cause
        assert "Access denied" in str(error)

    def test_is_agent_error(self) -> None:
        """DeploymentError is an AgentError subclass."""
        error = DeploymentError("target", "msg")
        assert isinstance(error, AgentError)


class TestDiscoveryError:
    """Test DiscoveryError exception."""

    def test_init_without_cause(self) -> None:
        """DiscoveryError with URL."""
        error = DiscoveryError("http://localhost:9001/.well-known/agent-configuration")

        assert error.url == "http://localhost:9001/.well-known/agent-configuration"
        assert error.cause is None
        assert error.code == "DISCOVERY_ERROR"
        assert error.recoverable is True

    def test_init_with_cause(self) -> None:
        """DiscoveryError with cause exception."""
        cause = ValueError("Invalid JSON")
        error = DiscoveryError("http://test", cause=cause)

        assert error.cause == cause
        assert "Invalid JSON" in str(error)

    def test_is_agent_error(self) -> None:
        """DiscoveryError is an AgentError subclass."""
        error = DiscoveryError("http://test")
        assert isinstance(error, AgentError)


class TestValidationError:
    """Test ValidationError exception."""

    def test_init(self) -> None:
        """ValidationError stores field and message."""
        error = ValidationError("port", "must be between 1 and 65535")

        assert error.field == "port"
        assert error.code == "VALIDATION"
        assert error.recoverable is False
        assert "port" in str(error)
        assert "1 and 65535" in str(error)

    def test_is_agent_error(self) -> None:
        """ValidationError is an AgentError subclass."""
        error = ValidationError("field", "message")
        assert isinstance(error, AgentError)


class TestExceptionRaising:
    """Test raising and catching exceptions."""

    def test_catch_specific_exception(self) -> None:
        """Can catch specific exception type."""
        with pytest.raises(ConnectionError) as exc_info:
            raise ConnectionError("http://test")

        assert exc_info.value.url == "http://test"

    def test_catch_base_agent_error(self) -> None:
        """Can catch all agent errors via base class."""
        errors_to_test = [
            ConnectionError("http://test"),
            TimeoutError("http://test", 10),
            SecurityError("test"),
            ConfigurationError("test"),
            AgentBackendError("test", "msg"),
            DeploymentError("target", "msg"),
            DiscoveryError("http://test"),
            ValidationError("field", "msg"),
        ]

        for error in errors_to_test:
            with pytest.raises(AgentError):
                raise error

    def test_catch_as_exception(self) -> None:
        """Can catch as generic Exception."""
        with pytest.raises(SecurityError):
            raise SecurityError("Test")
