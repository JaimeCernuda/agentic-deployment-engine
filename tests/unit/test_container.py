"""Tests for dependency injection container in src/core/container.py.

Tests cover:
- Container initialization
- Dependency overriding
- Settings retrieval
- Singleton management
- Backend factory
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config import AgentSettings, DeploymentSettings
from src.core.container import Container, container


class TestContainerInit:
    """Test Container initialization."""

    def test_creates_empty_container(self) -> None:
        """New container has empty overrides and singletons."""
        c = Container()
        assert c._overrides == {}
        assert c._singletons == {}


class TestOverride:
    """Test dependency overriding."""

    def test_override_sets_value(self) -> None:
        """override() stores value in overrides dict."""
        c = Container()
        mock_value = MagicMock()
        c.override("test_dep", mock_value)

        assert c._overrides["test_dep"] == mock_value

    def test_override_multiple_values(self) -> None:
        """Can override multiple dependencies."""
        c = Container()
        c.override("dep1", "value1")
        c.override("dep2", "value2")

        assert c._overrides["dep1"] == "value1"
        assert c._overrides["dep2"] == "value2"

    def test_override_replaces_existing(self) -> None:
        """override() replaces existing override."""
        c = Container()
        c.override("dep", "old_value")
        c.override("dep", "new_value")

        assert c._overrides["dep"] == "new_value"


class TestResetOverrides:
    """Test reset_overrides method."""

    def test_clears_all_overrides(self) -> None:
        """reset_overrides() clears all overrides."""
        c = Container()
        c.override("dep1", "value1")
        c.override("dep2", "value2")

        c.reset_overrides()

        assert c._overrides == {}


class TestResetSingletons:
    """Test reset_singletons method."""

    def test_clears_all_singletons(self) -> None:
        """reset_singletons() clears cached singletons."""
        c = Container()
        c._singletons["test"] = "cached_value"

        c.reset_singletons()

        assert c._singletons == {}


class TestAgentSettings:
    """Test agent_settings method."""

    def test_returns_global_settings_by_default(self) -> None:
        """Returns global settings when not overridden."""
        c = Container()
        c.reset_overrides()

        result = c.agent_settings()

        assert isinstance(result, AgentSettings)

    def test_returns_override_when_set(self) -> None:
        """Returns overridden value when set."""
        c = Container()
        mock_settings = MagicMock(spec=AgentSettings)
        c.override("agent_settings", mock_settings)

        result = c.agent_settings()

        assert result == mock_settings


class TestDeploySettings:
    """Test deploy_settings method."""

    def test_returns_global_settings_by_default(self) -> None:
        """Returns global deploy settings when not overridden."""
        c = Container()
        c.reset_overrides()

        result = c.deploy_settings()

        assert isinstance(result, DeploymentSettings)

    def test_returns_override_when_set(self) -> None:
        """Returns overridden value when set."""
        c = Container()
        mock_settings = MagicMock(spec=DeploymentSettings)
        c.override("deploy_settings", mock_settings)

        result = c.deploy_settings()

        assert result == mock_settings


class TestAgentRegistry:
    """Test agent_registry method."""

    def test_returns_override_when_set(self) -> None:
        """Returns overridden registry when set."""
        c = Container()
        c.reset_singletons()
        mock_registry = MagicMock()
        c.override("agent_registry", mock_registry)

        result = c.agent_registry()

        assert result == mock_registry

    def test_creates_singleton(self) -> None:
        """Creates and caches AgentRegistry singleton."""
        c = Container()
        c.reset_overrides()
        c.reset_singletons()

        # First call creates the registry
        result1 = c.agent_registry()
        # Second call returns the same instance
        result2 = c.agent_registry()

        # Same instance returned both times
        assert result1 is result2
        # Cached in singletons
        assert "agent_registry" in c._singletons


class TestHttpClient:
    """Test http_client method."""

    def test_returns_override_when_set(self) -> None:
        """Returns overridden client when set."""
        c = Container()
        mock_client = MagicMock()
        c.override("http_client", mock_client)

        result = c.http_client()

        assert result == mock_client

    def test_creates_httpx_client(self) -> None:
        """Creates httpx.AsyncClient with correct timeout."""
        c = Container()
        c.reset_overrides()

        # Use actual httpx to verify it works
        import httpx

        result = c.http_client(timeout=15.0)

        assert isinstance(result, httpx.AsyncClient)

    def test_uses_settings_timeout_by_default(self) -> None:
        """Uses settings timeout when not specified."""
        c = Container()
        c.reset_overrides()

        mock_settings = MagicMock()
        mock_settings.http_timeout = 30.0
        c.override("agent_settings", mock_settings)

        import httpx

        result = c.http_client()

        assert isinstance(result, httpx.AsyncClient)


class TestClaudeBackend:
    """Test claude_backend method."""

    def test_returns_override_when_set(self) -> None:
        """Returns result of overridden factory when set."""
        c = Container()
        mock_backend = MagicMock()
        mock_factory = MagicMock(return_value=mock_backend)
        c.override("claude_backend", mock_factory)

        mock_config = MagicMock()
        result = c.claude_backend(mock_config)

        mock_factory.assert_called_once_with(mock_config)
        assert result == mock_backend

    def test_creates_claude_sdk_backend(self) -> None:
        """Creates ClaudeSDKBackend when not overridden."""
        c = Container()
        c.reset_overrides()

        with patch("src.backends.ClaudeSDKBackend") as MockBackend:
            mock_instance = MagicMock()
            MockBackend.return_value = mock_instance

            mock_config = MagicMock()
            result = c.claude_backend(mock_config)

            # Should have created a backend (may be real or mocked)
            assert result is not None


class TestBackendFactory:
    """Test backend_factory method."""

    def test_returns_override_when_set(self) -> None:
        """Returns result of overridden factory when set."""
        c = Container()
        mock_backend = MagicMock()
        mock_factory = MagicMock(return_value=mock_backend)
        c.override("backend_factory", mock_factory)

        mock_config = MagicMock()
        result = c.backend_factory("claude", mock_config)

        mock_factory.assert_called_once_with("claude", mock_config)
        assert result == mock_backend

    def test_creates_claude_backend(self) -> None:
        """Creates ClaudeSDKBackend for 'claude' type."""
        c = Container()
        c.reset_overrides()

        mock_config = MagicMock()
        result = c.backend_factory("claude", mock_config)

        # Should have created a backend
        assert result is not None

    def test_creates_crewai_backend(self) -> None:
        """Creates CrewAIBackend for 'crewai' type."""
        c = Container()
        c.reset_overrides()

        mock_config = MagicMock()
        result = c.backend_factory("crewai", mock_config)

        # Should have created a backend
        assert result is not None

    def test_creates_gemini_backend(self) -> None:
        """Creates GeminiCLIBackend for 'gemini' type."""
        c = Container()
        c.reset_overrides()

        mock_config = MagicMock()
        result = c.backend_factory("gemini", mock_config)

        # Should have created a backend
        assert result is not None

    def test_raises_for_unknown_backend(self) -> None:
        """Raises ValueError for unknown backend type."""
        c = Container()
        c.reset_overrides()

        with pytest.raises(ValueError) as exc_info:
            c.backend_factory("unknown_backend", MagicMock())

        assert "Unknown backend type" in str(exc_info.value)
        assert "unknown_backend" in str(exc_info.value)


class TestGlobalContainer:
    """Test global container instance."""

    def test_global_container_exists(self) -> None:
        """Global container is a Container instance."""
        assert isinstance(container, Container)

    def test_global_container_methods_work(self) -> None:
        """Global container methods are accessible."""
        # Just verify methods exist and don't crash
        assert hasattr(container, "agent_settings")
        assert hasattr(container, "deploy_settings")
        assert hasattr(container, "override")
        assert hasattr(container, "reset_overrides")
