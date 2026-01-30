"""Tests for backend implementations.

Tests cover:
- ClaudeSDKBackend
- CrewAIBackend
- GeminiCLIBackend
- BackendConfig
- QueryResult
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backends.base import AgentBackend, BackendConfig, QueryResult


class TestBackendConfig:
    """Test BackendConfig dataclass."""

    def test_default_values(self) -> None:
        """BackendConfig has sensible defaults."""
        config = BackendConfig(name="test-backend")

        assert config.name == "test-backend"
        assert config.mcp_servers == {}
        assert config.allowed_tools == []
        assert config.system_prompt is None
        assert config.extra_options == {}

    def test_custom_values(self) -> None:
        """BackendConfig accepts custom values."""
        config = BackendConfig(
            name="custom-backend",
            mcp_servers={"server1": {}, "server2": {}},
            allowed_tools=["tool1", "tool2"],
            system_prompt="You are helpful.",
            extra_options={"key": "value"},
        )

        assert config.name == "custom-backend"
        assert "server1" in config.mcp_servers
        assert config.allowed_tools == ["tool1", "tool2"]
        assert config.system_prompt == "You are helpful."
        assert config.extra_options == {"key": "value"}


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_default_values(self) -> None:
        """QueryResult has sensible defaults."""
        result = QueryResult(response="Hello!")

        assert result.response == "Hello!"
        assert result.messages_count == 0
        assert result.tools_used == 0
        assert result.metadata == {}

    def test_custom_values(self) -> None:
        """QueryResult accepts custom values."""
        result = QueryResult(
            response="Test response",
            messages_count=5,
            tools_used=2,
            metadata={"key": "value"},
        )

        assert result.response == "Test response"
        assert result.messages_count == 5
        assert result.tools_used == 2
        assert result.metadata == {"key": "value"}


class TestAgentBackendBase:
    """Test AgentBackend abstract base class."""

    def test_is_abstract(self) -> None:
        """AgentBackend cannot be instantiated directly."""
        from collections.abc import AsyncIterator

        class ConcreteBackend(AgentBackend):
            @property
            def name(self) -> str:
                return "test"

            async def initialize(self) -> None:
                pass

            async def query(self, prompt, context=None):
                return QueryResult(response="test")

            async def query_stream(self, prompt, context=None) -> AsyncIterator:
                if False:
                    yield

            async def cleanup(self) -> None:
                pass

        config = BackendConfig(name="test")
        backend = ConcreteBackend(config)
        assert backend.config == config
        assert backend._initialized is False


class TestClaudeSDKBackend:
    """Test ClaudeSDKBackend."""

    def test_name_property(self) -> None:
        """name property returns correct name."""
        from src.backends.claude_sdk import ClaudeSDKBackend

        config = BackendConfig(name="test")
        backend = ClaudeSDKBackend(config)

        assert backend.name == "claude-agent-sdk"

    def test_init_creates_pool(self) -> None:
        """__init__ creates empty pool."""
        from src.backends.claude_sdk import ClaudeSDKBackend

        config = BackendConfig(name="test")
        backend = ClaudeSDKBackend(config)

        assert backend._pool is not None
        assert backend._options is None
        assert backend._initialized is False

    @pytest.mark.asyncio
    async def test_cleanup_when_not_initialized(self) -> None:
        """cleanup() does nothing when not initialized."""
        from src.backends.claude_sdk import ClaudeSDKBackend

        config = BackendConfig(name="test")
        backend = ClaudeSDKBackend(config)
        backend._initialized = False

        # Should not raise
        await backend.cleanup()

    @pytest.mark.asyncio
    async def test_update_system_prompt(self) -> None:
        """update_system_prompt() updates config and reinitializes."""
        from src.backends.claude_sdk import ClaudeSDKBackend

        config = BackendConfig(name="test", system_prompt="Original")
        backend = ClaudeSDKBackend(config)

        with patch.object(backend, "cleanup", new_callable=AsyncMock) as mock_cleanup:
            with patch.object(
                backend, "initialize", new_callable=AsyncMock
            ) as mock_init:
                await backend.update_system_prompt("New prompt")

                assert backend.config.system_prompt == "New prompt"
                mock_cleanup.assert_called_once()
                mock_init.assert_called_once()


class TestCrewAIBackend:
    """Test CrewAIBackend."""

    def test_name_property(self) -> None:
        """name property returns correct name."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test")
        backend = CrewAIBackend(config)

        assert backend.name == "crewai"

    def test_init_creates_backend(self) -> None:
        """__init__ creates backend."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test")
        backend = CrewAIBackend(config)

        assert backend._agent is None
        assert backend._llm is None
        assert backend._initialized is False

    @pytest.mark.asyncio
    async def test_cleanup_when_not_initialized(self) -> None:
        """cleanup() does nothing when not initialized."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test")
        backend = CrewAIBackend(config)
        backend._initialized = False

        # Should not raise
        await backend.cleanup()


class TestGeminiCLIBackend:
    """Test GeminiCLIBackend."""

    def test_name_property(self) -> None:
        """name property returns correct name."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test")
        backend = GeminiCLIBackend(config)

        assert backend.name == "gemini-cli"

    def test_init_creates_backend(self) -> None:
        """__init__ creates backend."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test")
        backend = GeminiCLIBackend(config)

        assert backend._initialized is False

    @pytest.mark.asyncio
    async def test_cleanup_when_not_initialized(self) -> None:
        """cleanup() does nothing when not initialized."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test")
        backend = GeminiCLIBackend(config)
        backend._initialized = False

        # Should not raise
        await backend.cleanup()


class TestBackendIntegration:
    """Integration-style tests for backends."""

    def test_all_backends_implement_interface(self) -> None:
        """All backends implement AgentBackend interface."""
        from src.backends.claude_sdk import ClaudeSDKBackend
        from src.backends.crewai import CrewAIBackend
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test")

        backends = [
            ClaudeSDKBackend(config),
            CrewAIBackend(config),
            GeminiCLIBackend(config),
        ]

        for backend in backends:
            assert isinstance(backend, AgentBackend)
            assert hasattr(backend, "name")
            assert hasattr(backend, "initialize")
            assert hasattr(backend, "query")
            assert hasattr(backend, "cleanup")

    def test_all_backends_have_name(self) -> None:
        """All backends return a name."""
        from src.backends.claude_sdk import ClaudeSDKBackend
        from src.backends.crewai import CrewAIBackend
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test")

        backends = [
            ClaudeSDKBackend(config),
            CrewAIBackend(config),
            GeminiCLIBackend(config),
        ]

        for backend in backends:
            assert isinstance(backend.name, str)
            assert len(backend.name) > 0
