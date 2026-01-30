#!/usr/bin/env python3
"""
Integration tests for A2A agents.
Tests each agent individually and multi-agent coordination.

These tests require running agents:
- Weather Agent on port 9001
- Maps Agent on port 9002
- Controller Agent on port 9000

Run with: uv run pytest -m integration
"""

from pathlib import Path

import httpx
import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestAgentEndpoints:
    """Test A2A protocol endpoints for all agents."""

    @pytest.mark.asyncio
    async def test_weather_agent_discovery(self):
        """Test Weather Agent A2A discovery endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:9001/.well-known/agent-configuration"
            )
            assert response.status_code == 200

            config = response.json()
            assert config["name"] == "Weather Agent"
            assert config["version"] == "1.0.0"
            assert config["capabilities"]["streaming"] is True
            assert len(config["skills"]) == 2

    @pytest.mark.asyncio
    async def test_maps_agent_discovery(self):
        """Test Maps Agent A2A discovery endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:9002/.well-known/agent-configuration"
            )
            assert response.status_code == 200

            config = response.json()
            assert config["name"] == "Maps Agent"
            assert config["version"] == "1.0.0"
            assert len(config["skills"]) == 2

    @pytest.mark.asyncio
    async def test_controller_agent_discovery(self):
        """Test Controller Agent A2A discovery endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:9000/.well-known/agent-configuration"
            )
            assert response.status_code == 200

            config = response.json()
            assert config["name"] == "Controller Agent"
            assert config["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_endpoints(self):
        """Test health endpoints for all agents."""
        agents = [
            ("Weather Agent", "http://localhost:9001"),
            ("Maps Agent", "http://localhost:9002"),
            ("Controller Agent", "http://localhost:9000"),
        ]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, url in agents:
                response = await client.get(f"{url}/health")
                assert response.status_code == 200

                health = response.json()
                assert health["status"] == "healthy"
                assert health["agent"] == name


class TestWeatherAgent:
    """Test Weather Agent functionality."""

    @pytest.mark.asyncio
    async def test_weather_query_tokyo(self):
        """Test weather query for Tokyo."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:9001/query",
                json={"query": "What's the weather in Tokyo?"},
            )
            assert response.status_code == 200

            result = response.json()
            assert "response" in result
            assert len(result["response"]) > 0
            assert (
                "Tokyo" in result["response"] or "tokyo" in result["response"].lower()
            )

    @pytest.mark.asyncio
    async def test_weather_locations(self):
        """Test getting weather locations."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:9001/query",
                json={"query": "What cities do you have weather data for?"},
            )
            assert response.status_code == 200

            result = response.json()
            # Should mention available cities
            assert any(
                city in result["response"]
                for city in ["Tokyo", "London", "Paris", "New York"]
            )


class TestMapsAgent:
    """Test Maps Agent functionality."""

    @pytest.mark.asyncio
    async def test_distance_query(self):
        """Test distance calculation query."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:9002/query",
                json={"query": "How far is Tokyo from London?"},
            )
            assert response.status_code == 200

            result = response.json()
            assert "response" in result
            assert len(result["response"]) > 0
            # Should mention both cities
            response_lower = result["response"].lower()
            assert "tokyo" in response_lower
            assert "london" in response_lower

    @pytest.mark.asyncio
    async def test_available_cities(self):
        """Test getting available cities."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:9002/query",
                json={"query": "What cities are available?"},
            )
            assert response.status_code == 200

            result = response.json()
            # Should list cities
            assert any(
                city in result["response"]
                for city in ["Tokyo", "London", "Paris", "New York"]
            )


class TestControllerAgent:
    """Test Controller Agent multi-agent coordination."""

    @pytest.mark.asyncio
    async def test_weather_delegation(self):
        """Test controller delegating to weather agent."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "http://localhost:9000/query",
                json={"query": "What is the weather in Paris?"},
            )
            assert response.status_code == 200

            result = response.json()
            assert "response" in result
            assert (
                "Paris" in result["response"] or "paris" in result["response"].lower()
            )
            # Should have weather info
            assert any(
                word in result["response"].lower()
                for word in ["temperature", "weather", "°c", "°f"]
            )

    @pytest.mark.asyncio
    async def test_maps_delegation(self):
        """Test controller delegating to maps agent."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "http://localhost:9000/query",
                json={"query": "How far is London from New York?"},
            )
            assert response.status_code == 200

            result = response.json()
            assert "response" in result
            response_lower = result["response"].lower()
            assert "london" in response_lower
            assert "new york" in response_lower
            # Should have distance info
            assert any(
                unit in result["response"] for unit in ["km", "miles", "kilometers"]
            )

    @pytest.mark.asyncio
    async def test_multi_agent_coordination(self):
        """Test controller coordinating multiple agents."""
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.post(
                "http://localhost:9000/query",
                json={
                    "query": "What's the weather in Tokyo and how far is it from London?"
                },
            )
            assert response.status_code == 200

            result = response.json()
            assert "response" in result
            response_lower = result["response"].lower()

            # Should have weather info
            assert "tokyo" in response_lower
            assert any(word in response_lower for word in ["temperature", "weather"])

            # Should have distance info
            assert "london" in response_lower
            assert any(unit in result["response"] for unit in ["km", "miles"])


class TestLogging:
    """Test that logging is working correctly."""

    def test_log_directory_exists(self):
        """Test that logs directory exists."""
        log_dir = Path(__file__).parent.parent.parent / "logs"
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_agent_log_files_exist(self):
        """Test that agent log files are created."""
        log_dir = Path(__file__).parent.parent.parent / "logs"

        expected_logs = ["weather_agent.log", "maps_agent.log", "controller_agent.log"]

        for log_file in expected_logs:
            log_path = log_dir / log_file
            # Log file should exist if agent was started
            if log_path.exists():
                assert log_path.is_file()
                # Should have some content
                assert log_path.stat().st_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
