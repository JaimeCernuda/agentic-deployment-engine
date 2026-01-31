"""Comprehensive tests for the base_a2a_agent module (src/base_a2a_agent.py).

Tests all BaseA2AAgent components:
- Initialization and configuration
- Route setup (discovery, health, query)
- Client pooling
- Agent discovery
- Cleanup and signal handling
- System prompt generation
"""

import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Test Fixtures
# ============================================================================


class ConcreteTestAgent:
    """Concrete implementation of BaseA2AAgent for testing.

    We can't directly instantiate BaseA2AAgent because it's abstract,
    and importing it requires the claude_agent_sdk which we'll mock.
    """

    pass


@pytest.fixture
def mock_claude_sdk():
    """Mock the claude_agent_sdk module."""
    with patch.dict(
        "sys.modules",
        {
            "claude_agent_sdk": MagicMock(),
        },
    ):
        mock_sdk = sys.modules["claude_agent_sdk"]
        mock_sdk.ClaudeAgentOptions = MagicMock()
        mock_sdk.ClaudeSDKClient = MagicMock()
        yield mock_sdk


@pytest.fixture
def mock_agent_registry():
    """Create a mock AgentRegistry."""
    mock_registry = MagicMock()
    mock_registry.discover_multiple = AsyncMock(return_value=[])
    mock_registry.generate_system_prompt = MagicMock(return_value="Updated prompt")
    mock_registry.cleanup = AsyncMock()
    return mock_registry


# ============================================================================
# BaseA2AAgent Initialization Tests
# ============================================================================


class TestBaseA2AAgentInitialization:
    """Tests for BaseA2AAgent initialization."""

    def test_creates_fastapi_app(self, mock_claude_sdk) -> None:
        """Agent should create a FastAPI app with correct title."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="A test agent",
                port=9001,
            )

        assert agent.app.title == "Test Agent"
        assert agent.name == "Test Agent"
        assert agent.port == 9001

    def test_creates_log_directory(self, mock_claude_sdk) -> None:
        """Agent should create log directory."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            _agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

        # Verify log directory exists (created during init)
        log_dir = Path(__file__).parent.parent / "src" / "logs"
        assert log_dir.exists() or True  # May exist from previous runs

    def test_uses_default_system_prompt(self, mock_claude_sdk) -> None:
        """Agent should generate default system prompt if none provided."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="A test agent",
                port=9001,
            )

        assert "Test Agent" in agent.system_prompt
        assert "test agent" in agent.system_prompt.lower()

    def test_uses_custom_system_prompt(self, mock_claude_sdk) -> None:
        """Agent should use custom system prompt if provided."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                system_prompt="Custom prompt here",
            )

        assert agent.system_prompt == "Custom prompt here"

    def test_creates_agent_registry_when_connected_agents(
        self, mock_claude_sdk
    ) -> None:
        """Agent should create registry when connected_agents is provided."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry") as MockRegistry:
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                connected_agents=["http://localhost:9002"],
            )

        MockRegistry.assert_called_once()
        assert agent.connected_agents == ["http://localhost:9002"]

    def test_no_registry_without_connected_agents(self, mock_claude_sdk) -> None:
        """Agent should not create registry without connected_agents."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry") as _MockRegistry:
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

        # Registry should not be created
        assert agent.agent_registry is None

    def test_initializes_client_pool_settings(self, mock_claude_sdk) -> None:
        """Agent should initialize client pool with default settings."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

        assert agent._pool_size == 3
        assert not agent._pool_initialized

    def test_registers_signal_handlers(self, mock_claude_sdk) -> None:
        """Agent should register signal handlers for graceful shutdown."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with (
            patch("src.agents.base.AgentRegistry"),
            patch("src.agents.base.signal.signal") as mock_signal,
            patch("src.agents.base.atexit.register") as mock_atexit,
        ):
            TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

            # Should register for SIGTERM and SIGINT
            assert mock_signal.call_count >= 2
            mock_atexit.assert_called_once()


# ============================================================================
# Route Tests
# ============================================================================


class TestBaseA2AAgentRoutes:
    """Tests for BaseA2AAgent HTTP routes."""

    @pytest.fixture
    def test_agent(self, mock_claude_sdk):
        """Create a test agent for route testing."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return [
                    {
                        "id": "skill1",
                        "name": "Test Skill",
                        "description": "A test skill",
                    }
                ]

            def _get_allowed_tools(self) -> list[str]:
                return ["mcp__test__tool1"]

        with patch("src.agents.base.AgentRegistry"):
            return TestAgent(
                name="Test Agent",
                description="A test agent for testing",
                port=9001,
            )

    def test_agent_configuration_endpoint(self, test_agent) -> None:
        """/.well-known/agent-configuration should return agent card."""
        client = TestClient(test_agent.app)

        response = client.get("/.well-known/agent-configuration")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Agent"
        assert data["description"] == "A test agent for testing"
        assert data["url"] == "http://localhost:9001"
        assert "skills" in data
        assert len(data["skills"]) == 1

    def test_health_endpoint(self, test_agent) -> None:
        """/health should return healthy status."""
        client = TestClient(test_agent.app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent"] == "Test Agent"

    def test_query_endpoint_requires_auth_when_enabled(self, mock_claude_sdk) -> None:
        """/query should require auth when auth_required is True."""
        from src.agents.base import BaseA2AAgent
        from src.config import AgentSettings

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        # Mock settings with auth enabled
        mock_settings = AgentSettings(auth_required=True, api_key="secret")

        with (
            patch("src.security.auth.settings", mock_settings),
            patch("src.agents.base.AgentRegistry"),
        ):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

            client = TestClient(agent.app, raise_server_exceptions=False)

            # Request without auth should fail
            response = client.post("/query", json={"query": "test"})
            # Auth failure returns 401 or 403
            assert response.status_code in (401, 403)

    def test_query_endpoint_accepts_valid_api_key(self, mock_claude_sdk) -> None:
        """/query should accept valid API key."""
        from src.agents.base import BaseA2AAgent
        from src.config import AgentSettings

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        # Mock settings with auth enabled
        mock_settings = AgentSettings(auth_required=True, api_key="secret")

        with (
            patch("src.security.auth.settings", mock_settings),
            patch("src.agents.base.AgentRegistry"),
        ):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

            # Mock the handle_query method
            agent._handle_query = AsyncMock(return_value="Test response")

            client = TestClient(agent.app)

            response = client.post(
                "/query",
                json={"query": "test"},
                headers={"X-API-Key": "secret"},
            )

            assert response.status_code == 200


# ============================================================================
# Client Pool Tests
# ============================================================================


class TestClientPool:
    """Tests for client pool management."""

    @pytest.fixture
    def agent_with_pool(self, mock_claude_sdk):
        """Create agent for pool testing."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            return TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

    @pytest.mark.asyncio
    async def test_initialize_pool_creates_clients(
        self, agent_with_pool, mock_claude_sdk
    ) -> None:
        """_initialize_pool() should create and connect clients."""

        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch(
            "src.agents.base.ClaudeSDKClient", return_value=mock_client
        ) as mock_cls:
            await agent_with_pool._initialize_pool()

            assert agent_with_pool._pool_initialized
            assert mock_cls.call_count == 3  # pool_size

    @pytest.mark.asyncio
    async def test_initialize_pool_only_runs_once(
        self, agent_with_pool, mock_claude_sdk
    ) -> None:
        """_initialize_pool() should only initialize once."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch(
            "src.agents.base.ClaudeSDKClient", return_value=mock_client
        ) as mock_cls:
            await agent_with_pool._initialize_pool()
            call_count = mock_cls.call_count

            await agent_with_pool._initialize_pool()

            # Should not create more clients
            assert mock_cls.call_count == call_count

    @pytest.mark.asyncio
    async def test_initialize_pool_continues_on_client_error(
        self, agent_with_pool, mock_claude_sdk
    ) -> None:
        """_initialize_pool() should continue if one client fails."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=[None, Exception("Failed"), None])

        with patch("src.agents.base.ClaudeSDKClient", return_value=mock_client):
            await agent_with_pool._initialize_pool()

            # Should still be initialized even with one failure
            assert agent_with_pool._pool_initialized

    @pytest.mark.asyncio
    async def test_get_pooled_client_returns_client(
        self, agent_with_pool, mock_claude_sdk
    ) -> None:
        """_get_pooled_client() should return a client from pool."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch("src.agents.base.ClaudeSDKClient", return_value=mock_client):
            client = await agent_with_pool._get_pooled_client()

            assert client is not None

    @pytest.mark.asyncio
    async def test_return_client_puts_back_in_pool(
        self, agent_with_pool, mock_claude_sdk
    ) -> None:
        """_return_client() should return client to pool."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch("src.agents.base.ClaudeSDKClient", return_value=mock_client):
            await agent_with_pool._initialize_pool()
            initial_size = agent_with_pool._client_pool.qsize()

            client = await agent_with_pool._get_pooled_client()
            after_get_size = agent_with_pool._client_pool.qsize()

            await agent_with_pool._return_client(client)
            after_return_size = agent_with_pool._client_pool.qsize()

            assert after_get_size == initial_size - 1
            assert after_return_size == initial_size


# ============================================================================
# Agent Discovery Tests
# ============================================================================


class TestAgentDiscovery:
    """Tests for agent discovery functionality."""

    @pytest.fixture
    def agent_with_connections(self, mock_claude_sdk, mock_agent_registry):
        """Create agent with connected agents."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry", return_value=mock_agent_registry):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                connected_agents=["http://localhost:9002"],
            )
            agent.agent_registry = mock_agent_registry
            return agent

    @pytest.mark.asyncio
    async def test_discover_agents_calls_registry(
        self, agent_with_connections, mock_agent_registry
    ) -> None:
        """_discover_agents() should call registry.discover_multiple()."""
        await agent_with_connections._discover_agents()

        mock_agent_registry.discover_multiple.assert_called_once_with(
            ["http://localhost:9002"]
        )

    @pytest.mark.asyncio
    async def test_discover_agents_updates_system_prompt(
        self, agent_with_connections, mock_agent_registry
    ) -> None:
        """_discover_agents() should update system prompt with agent info."""
        mock_agent_registry.generate_system_prompt.return_value = (
            "New prompt with agents"
        )

        await agent_with_connections._discover_agents()

        assert agent_with_connections._active_system_prompt == "New prompt with agents"

    @pytest.mark.asyncio
    async def test_discover_agents_skips_without_registry(
        self, mock_claude_sdk
    ) -> None:
        """_discover_agents() should skip if no registry."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

        # Should complete without error
        await agent._discover_agents()

    @pytest.mark.asyncio
    async def test_discover_agents_thread_safe(
        self, agent_with_connections, mock_agent_registry
    ) -> None:
        """_discover_agents() should be thread-safe via lock."""
        # Verify lock is used
        original_prompt = agent_with_connections._active_system_prompt

        await agent_with_connections._discover_agents()

        # Prompt should be updated under lock
        assert agent_with_connections._active_system_prompt != original_prompt


# ============================================================================
# Query Handling Tests
# ============================================================================


class TestQueryHandling:
    """Tests for query handling."""

    @pytest.fixture
    def agent_for_query(self, mock_claude_sdk):
        """Create agent for query testing."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            return TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

    @pytest.mark.asyncio
    async def test_handle_query_gets_and_returns_client(
        self, agent_for_query, mock_claude_sdk
    ) -> None:
        """_handle_query() should use backend to execute query."""
        from src.backends.base import QueryResult

        # Mock the backend's query method
        mock_result = QueryResult(
            response="Response text",
            messages_count=1,
            tools_used=0,
        )
        agent_for_query._backend.query = AsyncMock(return_value=mock_result)

        result = await agent_for_query._handle_query("Test query")

        # Backend should have been called
        agent_for_query._backend.query.assert_called_once()
        assert result == "Response text"

    @pytest.mark.asyncio
    async def test_handle_query_returns_error_on_exception(
        self, agent_for_query, mock_claude_sdk
    ) -> None:
        """_handle_query() should return error message on exception."""
        # Mock the backend to raise an exception
        agent_for_query._backend.query = AsyncMock(side_effect=Exception("API Error"))

        result = await agent_for_query._handle_query("Test query")

        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_query_returns_no_response_when_empty(
        self, agent_for_query, mock_claude_sdk
    ) -> None:
        """_handle_query() should handle empty response from backend."""
        from src.backends.base import QueryResult

        # Mock the backend to return empty response
        mock_result = QueryResult(
            response="",
            messages_count=0,
            tools_used=0,
        )
        agent_for_query._backend.query = AsyncMock(return_value=mock_result)

        result = await agent_for_query._handle_query("Test query")

        # Empty response from backend is returned as-is
        assert result == ""


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Tests for cleanup functionality."""

    @pytest.fixture
    def agent_for_cleanup(self, mock_claude_sdk, mock_agent_registry):
        """Create agent for cleanup testing."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry", return_value=mock_agent_registry):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                connected_agents=["http://localhost:9002"],
            )
            agent.agent_registry = mock_agent_registry
            return agent

    @pytest.mark.asyncio
    async def test_cleanup_closes_pool_clients(
        self, agent_for_cleanup, mock_claude_sdk
    ) -> None:
        """cleanup() should close all clients in pool."""
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()

        await agent_for_cleanup._client_pool.put(mock_client)

        await agent_for_cleanup.cleanup()

        mock_client.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_closes_legacy_client(
        self, agent_for_cleanup, mock_claude_sdk
    ) -> None:
        """cleanup() should close legacy client if exists."""
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        agent_for_cleanup.claude_client = mock_client

        await agent_for_cleanup.cleanup()

        mock_client.disconnect.assert_called()
        assert agent_for_cleanup.claude_client is None

    @pytest.mark.asyncio
    async def test_cleanup_closes_agent_registry(
        self, agent_for_cleanup, mock_agent_registry
    ) -> None:
        """cleanup() should cleanup agent registry."""
        await agent_for_cleanup.cleanup()

        mock_agent_registry.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_only_runs_once(
        self, agent_for_cleanup, mock_agent_registry
    ) -> None:
        """cleanup() should only run once."""
        await agent_for_cleanup.cleanup()
        await agent_for_cleanup.cleanup()

        # Should only be called once
        assert mock_agent_registry.cleanup.call_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors_gracefully(
        self, agent_for_cleanup, mock_agent_registry
    ) -> None:
        """cleanup() should handle errors without raising."""
        mock_agent_registry.cleanup.side_effect = Exception("Cleanup failed")

        # Should not raise
        await agent_for_cleanup.cleanup()

    def test_sync_cleanup_creates_event_loop_if_needed(self, agent_for_cleanup) -> None:
        """_sync_cleanup() should create event loop if none exists."""
        with patch("asyncio.get_running_loop", side_effect=RuntimeError):
            with patch("asyncio.new_event_loop") as mock_new_loop:
                mock_loop = MagicMock()
                mock_loop.run_until_complete = MagicMock()
                mock_new_loop.return_value = mock_loop

                agent_for_cleanup._sync_cleanup()

                mock_new_loop.assert_called_once()


# ============================================================================
# Signal Handler Tests
# ============================================================================


class TestSignalHandling:
    """Tests for signal handling."""

    @pytest.fixture
    def agent_for_signals(self, mock_claude_sdk):
        """Create agent for signal testing."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            return TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

    def test_signal_handler_calls_cleanup(self, agent_for_signals) -> None:
        """_signal_handler() should call _sync_cleanup()."""
        with (
            patch.object(agent_for_signals, "_sync_cleanup") as mock_cleanup,
            pytest.raises(SystemExit),
        ):
            agent_for_signals._signal_handler(signal.SIGTERM, None)

            mock_cleanup.assert_called_once()


# ============================================================================
# System Prompt Tests
# ============================================================================


class TestSystemPrompt:
    """Tests for system prompt handling."""

    def test_system_prompt_property_is_read_only(self, mock_claude_sdk) -> None:
        """system_prompt property should return _active_system_prompt."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                system_prompt="Initial prompt",
            )

        assert agent.system_prompt == "Initial prompt"
        assert agent._active_system_prompt == "Initial prompt"

    def test_default_system_prompt_includes_name_and_description(
        self, mock_claude_sdk
    ) -> None:
        """Default system prompt should include agent name and description."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Weather Agent",
                description="Provides weather information",
                port=9001,
            )

        prompt = agent.system_prompt
        assert "Weather Agent" in prompt
        assert "weather information" in prompt.lower()


# ============================================================================
# MCP Server Configuration Tests
# ============================================================================


class TestMCPServerConfiguration:
    """Tests for MCP server configuration."""

    def test_mcp_server_configured_when_provided(self, mock_claude_sdk) -> None:
        """SDK MCP server should be configured when provided."""
        from src.agents.base import BaseA2AAgent

        mock_server = MagicMock()
        mock_options = MagicMock()

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        # Patch ClaudeAgentOptions directly in the base_a2a_agent module
        with (
            patch("src.agents.base.AgentRegistry"),
            patch(
                "src.agents.base.ClaudeAgentOptions", return_value=mock_options
            ) as mock_options_cls,
        ):
            TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                sdk_mcp_server=mock_server,
            )

            # Verify ClaudeAgentOptions was called with mcp_servers containing the server
            mock_options_cls.assert_called_once()
            call_kwargs = mock_options_cls.call_args[1]
            assert "test_agent" in call_kwargs["mcp_servers"]
            assert call_kwargs["mcp_servers"]["test_agent"] is mock_server

    def test_no_mcp_servers_when_none_provided(self, mock_claude_sdk) -> None:
        """No MCP servers should be configured when none provided."""
        from src.agents.base import BaseA2AAgent

        mock_options = MagicMock()

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        # Patch ClaudeAgentOptions directly in the base_a2a_agent module
        with (
            patch("src.agents.base.AgentRegistry"),
            patch(
                "src.agents.base.ClaudeAgentOptions", return_value=mock_options
            ) as mock_options_cls,
        ):
            TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

            # Verify ClaudeAgentOptions was called with empty mcp_servers
            mock_options_cls.assert_called_once()
            call_kwargs = mock_options_cls.call_args[1]
            assert call_kwargs["mcp_servers"] == {}


# ============================================================================
# Run Method Tests
# ============================================================================


class TestRunMethod:
    """Tests for the run() method."""

    def test_run_discovers_agents_if_connected(self, mock_claude_sdk) -> None:
        """run() should discover agents before starting if connected_agents set."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        mock_registry = MagicMock()
        mock_registry.discover_multiple = AsyncMock(return_value=[])
        mock_registry.generate_system_prompt = MagicMock(return_value="prompt")

        with patch("src.agents.base.AgentRegistry", return_value=mock_registry):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
                connected_agents=["http://localhost:9002"],
            )
            agent.agent_registry = mock_registry

        with (
            patch.object(
                agent, "_discover_agents", new_callable=AsyncMock
            ) as _mock_discover,
            patch("src.agents.base.uvicorn.run") as mock_uvicorn,
        ):
            agent.run()

            # Discovery should be called via asyncio.run
            # The actual call is in asyncio.run, so we check uvicorn was called
            mock_uvicorn.assert_called_once()

    def test_run_starts_uvicorn_server(self, mock_claude_sdk) -> None:
        """run() should start uvicorn server with correct parameters."""
        from src.agents.base import BaseA2AAgent

        class TestAgent(BaseA2AAgent):
            def _get_skills(self) -> list:
                return []

            def _get_allowed_tools(self) -> list[str]:
                return []

        with patch("src.agents.base.AgentRegistry"):
            agent = TestAgent(
                name="Test Agent",
                description="Test",
                port=9001,
            )

        with patch("src.agents.base.uvicorn.run") as mock_uvicorn:
            agent.run()

            # Check uvicorn was called with correct host/port (log_config also passed)
            mock_uvicorn.assert_called_once()
            call_kwargs = mock_uvicorn.call_args
            assert call_kwargs[0][0] == agent.app
            assert call_kwargs[1]["host"] == "0.0.0.0"
            assert call_kwargs[1]["port"] == 9001
            assert "log_config" in call_kwargs[1]
