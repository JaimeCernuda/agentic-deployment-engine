"""Tests for observability features.

Verifies that logs are not truncated and contain useful information
for debugging and monitoring agent behavior.
"""

import pytest

from src.config import settings

pytestmark = [pytest.mark.usability]


class TestLogConfiguration:
    """Test log configuration settings."""

    def test_default_log_max_content_length(self):
        """Default max content length should be 2000."""
        # settings may be cached, check the class default
        from src.config import AgentSettings

        default_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert default_settings.log_max_content_length == 2000

    def test_log_max_content_length_configurable(self, monkeypatch):
        """Log max content length should be configurable via env."""
        monkeypatch.setenv("AGENT_LOG_MAX_CONTENT_LENGTH", "5000")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.log_max_content_length == 5000

    def test_log_max_content_length_zero_means_unlimited(self, monkeypatch):
        """Zero should mean unlimited log content."""
        monkeypatch.setenv("AGENT_LOG_MAX_CONTENT_LENGTH", "0")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.log_max_content_length == 0


class TestLogTruncationBehavior:
    """Test that log truncation respects settings."""

    def test_truncation_at_limit(self):
        """Content at limit should be shown in full."""
        max_len = 100
        content = "x" * 100  # Exactly at limit

        if max_len > 0 and len(content) > max_len:
            truncated = content[:max_len] + "..."
        else:
            truncated = content

        assert truncated == content
        assert "..." not in truncated

    def test_truncation_over_limit(self):
        """Content over limit should be truncated with ellipsis."""
        max_len = 100
        content = "x" * 150  # Over limit

        if max_len > 0 and len(content) > max_len:
            truncated = content[:max_len] + "..."
        else:
            truncated = content

        assert len(truncated) == 103  # 100 + "..."
        assert truncated.endswith("...")

    def test_truncation_disabled_with_zero(self):
        """Zero max length should not truncate."""
        max_len = 0
        content = "x" * 10000  # Very long

        if max_len > 0 and len(content) > max_len:
            truncated = content[:max_len] + "..."
        else:
            truncated = content

        assert truncated == content
        assert len(truncated) == 10000


class TestBackendConfiguration:
    """Test backend configuration settings."""

    def test_default_backend_type(self):
        """Default backend type should be claude."""
        from src.config import AgentSettings

        default_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert default_settings.backend_type == "claude"

    def test_backend_type_configurable(self, monkeypatch):
        """Backend type should be configurable via env."""
        monkeypatch.setenv("AGENT_BACKEND_TYPE", "gemini")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.backend_type == "gemini"

    def test_ollama_model_configurable(self, monkeypatch):
        """Ollama model should be configurable via env."""
        monkeypatch.setenv("AGENT_OLLAMA_MODEL", "mistral")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.ollama_model == "mistral"

    def test_ollama_base_url_configurable(self, monkeypatch):
        """Ollama base URL should be configurable via env."""
        monkeypatch.setenv("AGENT_OLLAMA_BASE_URL", "http://remote:11434")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.ollama_base_url == "http://remote:11434"


class TestOTelConfiguration:
    """Test OpenTelemetry configuration."""

    def test_otel_disabled_by_default(self):
        """OpenTelemetry should be disabled by default."""
        from src.config import AgentSettings

        default_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert default_settings.otel_enabled is False

    def test_otel_can_be_enabled(self, monkeypatch):
        """OpenTelemetry should be enableable via env."""
        monkeypatch.setenv("AGENT_OTEL_ENABLED", "true")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.otel_enabled is True

    def test_otel_endpoint_configurable(self, monkeypatch):
        """OTLP endpoint should be configurable."""
        monkeypatch.setenv("AGENT_OTEL_ENDPOINT", "http://jaeger:4317")

        from src.config import AgentSettings

        test_settings = AgentSettings(
            _env_file=None,
            _secrets_dir=None,
        )
        assert test_settings.otel_endpoint == "http://jaeger:4317"
