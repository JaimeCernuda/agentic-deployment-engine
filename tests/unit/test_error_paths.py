"""Error path tests for A2A transport and agent operations.

Tests error handling for:
- Invalid URLs
- Blocked URLs (SSRF)
- Empty parameters
- Agent registry errors
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.transport import discover_agent, is_safe_url, query_agent
from src.agents.registry import AgentRegistry

# The @tool decorator wraps the function - get the actual handler
query_agent_handler = query_agent.handler
discover_agent_handler = discover_agent.handler


class TestQueryAgentErrors:
    """Tests for error handling in query_agent."""

    @pytest.mark.asyncio
    async def test_invalid_url_returns_error(self) -> None:
        """Invalid/blocked URL should return an error response."""
        result = await query_agent_handler(
            {
                "agent_url": "http://169.254.169.254/",
                "query": "test",
            }
        )

        assert result["is_error"] is True
        assert "Invalid or blocked" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_empty_url_returns_error(self) -> None:
        """Empty URL should return an error response."""
        result = await query_agent_handler(
            {
                "agent_url": "",
                "query": "test",
            }
        )

        assert result["is_error"] is True
        assert "agent_url is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self) -> None:
        """Empty query should return an error response."""
        result = await query_agent_handler(
            {
                "agent_url": "http://localhost:9001",
                "query": "",
            }
        )

        assert result["is_error"] is True
        assert "query is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_blocked_internal_ip_returns_error(self) -> None:
        """Internal IP addresses should be blocked."""
        result = await query_agent_handler(
            {
                "agent_url": "http://10.0.0.1:9000/",
                "query": "test",
            }
        )

        assert result["is_error"] is True
        assert "Invalid or blocked" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_blocked_port_returns_error(self) -> None:
        """Ports outside allowed range should be blocked."""
        result = await query_agent_handler(
            {
                "agent_url": "http://localhost:80/",
                "query": "test",
            }
        )

        assert result["is_error"] is True
        assert "Invalid or blocked" in result["content"][0]["text"]


class TestDiscoverAgentErrors:
    """Tests for error handling in discover_agent."""

    @pytest.mark.asyncio
    async def test_empty_url_returns_error(self) -> None:
        """Empty URL should return an error response."""
        result = await discover_agent_handler(
            {
                "agent_url": "",
            }
        )

        assert result["is_error"] is True
        assert "agent_url is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_blocked_url_returns_error(self) -> None:
        """Blocked URL should return an error response."""
        result = await discover_agent_handler(
            {
                "agent_url": "http://10.0.0.1:9000/",
            }
        )

        assert result["is_error"] is True
        assert "Invalid or blocked" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_aws_metadata_blocked(self) -> None:
        """AWS metadata service URL should be blocked."""
        result = await discover_agent_handler(
            {
                "agent_url": "http://169.254.169.254/",
            }
        )

        assert result["is_error"] is True
        assert "Invalid or blocked" in result["content"][0]["text"]


class TestAgentRegistryErrors:
    """Tests for error handling in AgentRegistry."""

    @pytest.mark.asyncio
    async def test_discover_agent_connection_error(self) -> None:
        """Registry should handle connection errors gracefully."""
        registry = AgentRegistry()

        with patch.object(registry, "_client") as mock_client:
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result = await registry.discover_agent("http://localhost:9999")

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_agent_timeout(self) -> None:
        """Registry should handle timeouts gracefully."""
        registry = AgentRegistry()

        with patch.object(registry, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

            result = await registry.discover_agent("http://localhost:9999")

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_agent_http_error(self) -> None:
        """Registry should handle HTTP errors gracefully."""
        registry = AgentRegistry()

        with patch.object(registry, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Service Unavailable",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await registry.discover_agent("http://localhost:9999")

            assert result is None

    @pytest.mark.asyncio
    async def test_discover_multiple_partial_failure(self) -> None:
        """discover_multiple should return successful discoveries even if some fail."""
        registry = AgentRegistry()

        async def mock_discover(url: str):
            if "good" in url:
                from src.agents.registry import AgentInfo

                return AgentInfo(url, {"name": "Good Agent"})
            return None

        with patch.object(registry, "discover_agent", side_effect=mock_discover):
            results = await registry.discover_multiple(
                [
                    "http://localhost:9001/good",
                    "http://localhost:9002/bad",
                    "http://localhost:9003/good",
                ]
            )

            assert len(results) == 2


class TestIsSafeUrlEdgeCases:
    """Tests for edge cases in URL validation."""

    def test_handles_url_with_path(self) -> None:
        """URL with path should be checked correctly."""
        assert is_safe_url("http://localhost:9001/query") is True
        assert is_safe_url("http://localhost:9001/deep/path/here") is True

    def test_handles_url_with_query_string(self) -> None:
        """URL with query string should be checked correctly."""
        assert is_safe_url("http://localhost:9001/?foo=bar") is True
        assert is_safe_url("http://localhost:9001/path?key=value") is True

    def test_handles_url_with_fragment(self) -> None:
        """URL with fragment should be checked correctly."""
        assert is_safe_url("http://localhost:9001/#section") is True

    def test_handles_ipv6_localhost(self) -> None:
        """IPv6 localhost should be handled."""
        # Note: Behavior depends on implementation
        # Just ensure no crash - actual policy may vary
        is_safe_url("http://[::1]:9001/")

    def test_handles_username_in_url(self) -> None:
        """URL with username should be handled safely."""
        # URLs with credentials could be used for attacks
        # Behavior may vary - ensure no crash
        is_safe_url("http://user:pass@localhost:9001/")

    def test_handles_very_long_url(self) -> None:
        """Very long URL should not cause issues."""
        long_path = "a" * 10000
        # Should handle gracefully
        is_safe_url(f"http://localhost:9001/{long_path}")

    def test_handles_special_characters_in_path(self) -> None:
        """Special characters in path should be handled."""
        assert is_safe_url("http://localhost:9001/path%20with%20spaces") is True
        # Path traversal in URL path - should still validate host/port
        is_safe_url("http://localhost:9001/../../../etc/passwd")


class TestNetworkErrorRecovery:
    """Tests for graceful error recovery."""

    @pytest.mark.asyncio
    async def test_query_agent_returns_dict_on_error(self) -> None:
        """query_agent should always return a properly structured dict."""
        # Invalid URL
        result = await query_agent_handler({"agent_url": "not-a-url", "query": "test"})
        assert isinstance(result, dict)
        assert "content" in result
        assert "is_error" in result

    @pytest.mark.asyncio
    async def test_discover_agent_returns_dict_on_error(self) -> None:
        """discover_agent should always return a properly structured dict."""
        result = await discover_agent_handler({"agent_url": ""})
        assert isinstance(result, dict)
        assert "content" in result
        assert "is_error" in result

    @pytest.mark.asyncio
    async def test_registry_doesnt_cache_failed_discoveries(self) -> None:
        """Failed discoveries should not be cached."""
        registry = AgentRegistry()

        with patch.object(registry, "_client") as mock_client:
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            await registry.discover_agent("http://localhost:9999")

            # Agent should not be in cache
            assert registry.get_agent("http://localhost:9999") is None
            assert len(registry.list_agents()) == 0
