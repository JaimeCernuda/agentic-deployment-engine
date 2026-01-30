"""Comprehensive tests for agents/ modules.

Tests all agent implementations including:
- WeatherAgent initialization and skills
- MapsAgent initialization and skills
- ControllerAgent initialization and coordination
- Agent configuration and environment variables
- Edge cases and error handling
"""

import os
from unittest.mock import MagicMock, patch


class TestWeatherAgent:
    """Tests for WeatherAgent class."""

    def test_init_creates_agent_with_default_port(self) -> None:
        """Should create WeatherAgent on port 9001 by default."""
        with patch(
            "examples.agents.weather_agent.create_sdk_mcp_server"
        ) as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.weather_agent import WeatherAgent

                _agent = WeatherAgent()

                # Verify SDK server was created with correct name
                mock_create.assert_called_once()
                call_kwargs = mock_create.call_args[1]
                assert call_kwargs["name"] == "weather_agent"
                assert call_kwargs["version"] == "1.0.0"

    def test_init_accepts_custom_port(self) -> None:
        """Should accept custom port configuration."""
        with patch(
            "examples.agents.weather_agent.create_sdk_mcp_server"
        ) as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__"
            ) as mock_init:
                mock_init.return_value = None
                from examples.agents.weather_agent import WeatherAgent

                _agent = WeatherAgent(port=8080)

                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["port"] == 8080

    def test_get_skills_returns_weather_skills(self) -> None:
        """Should return weather-related skills."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.weather_agent import WeatherAgent

                agent = WeatherAgent()
                skills = agent._get_skills()

                assert len(skills) == 2
                skill_ids = [s["id"] for s in skills]
                assert "weather_analysis" in skill_ids
                assert "weather_locations" in skill_ids

    def test_get_skills_has_examples(self) -> None:
        """Skills should include usage examples."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.weather_agent import WeatherAgent

                agent = WeatherAgent()
                skills = agent._get_skills()

                for skill in skills:
                    assert "examples" in skill
                    assert len(skill["examples"]) > 0

    def test_get_allowed_tools_returns_mcp_tools(self) -> None:
        """Should return MCP tool names for SDK integration."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.weather_agent import WeatherAgent

                agent = WeatherAgent()
                tools = agent._get_allowed_tools()

                assert len(tools) == 2
                assert "mcp__weather_agent__get_weather" in tools
                assert "mcp__weather_agent__get_locations" in tools

    def test_system_prompt_includes_tool_instructions(self) -> None:
        """System prompt should include tool usage instructions."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.weather_agent.BaseA2AAgent.__init__"
            ) as mock_init:
                mock_init.return_value = None
                from examples.agents.weather_agent import WeatherAgent

                _agent = WeatherAgent()

                call_kwargs = mock_init.call_args[1]
                prompt = call_kwargs["system_prompt"]

                assert "mcp__weather_agent__get_weather" in prompt
                assert "mcp__weather_agent__get_locations" in prompt


class TestMapsAgent:
    """Tests for MapsAgent class."""

    def test_init_creates_agent_with_default_port(self) -> None:
        """Should create MapsAgent on port 9002 by default."""
        with patch("examples.agents.maps_agent.create_sdk_mcp_server") as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            with patch(
                "examples.agents.maps_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.maps_agent import MapsAgent

                _agent = MapsAgent()

                mock_create.assert_called_once()
                call_kwargs = mock_create.call_args[1]
                assert call_kwargs["name"] == "maps_agent"

    def test_init_accepts_custom_port(self) -> None:
        """Should accept custom port configuration."""
        with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
            with patch("examples.agents.maps_agent.BaseA2AAgent.__init__") as mock_init:
                mock_init.return_value = None
                from examples.agents.maps_agent import MapsAgent

                _agent = MapsAgent(port=7070)

                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["port"] == 7070

    def test_get_skills_returns_maps_skills(self) -> None:
        """Should return maps-related skills."""
        with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.maps_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.maps_agent import MapsAgent

                agent = MapsAgent()
                skills = agent._get_skills()

                assert len(skills) == 2
                skill_ids = [s["id"] for s in skills]
                assert "distance_calculation" in skill_ids
                assert "city_locations" in skill_ids

    def test_get_skills_includes_tags(self) -> None:
        """Skills should include searchable tags."""
        with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.maps_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.maps_agent import MapsAgent

                agent = MapsAgent()
                skills = agent._get_skills()

                for skill in skills:
                    assert "tags" in skill
                    assert len(skill["tags"]) > 0

    def test_get_allowed_tools_returns_mcp_tools(self) -> None:
        """Should return MCP tool names for SDK integration."""
        with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
            with patch(
                "examples.agents.maps_agent.BaseA2AAgent.__init__", return_value=None
            ):
                from examples.agents.maps_agent import MapsAgent

                agent = MapsAgent()
                tools = agent._get_allowed_tools()

                assert len(tools) == 2
                assert "mcp__maps_agent__get_distance" in tools
                assert "mcp__maps_agent__get_cities" in tools


class TestControllerAgent:
    """Tests for ControllerAgent class."""

    def test_init_creates_agent_with_default_port(self) -> None:
        """Should create ControllerAgent on port 9000 by default."""
        with patch(
            "examples.agents.controller_agent.create_a2a_transport_server"
        ) as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            with patch(
                "examples.agents.controller_agent.BaseA2AAgent.__init__"
            ) as mock_init:
                mock_init.return_value = None
                from examples.agents.controller_agent import ControllerAgent

                _agent = ControllerAgent()

                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["port"] == 9000

    def test_init_with_default_connected_agents(self) -> None:
        """Should connect to default Weather and Maps agents."""
        with patch("examples.agents.controller_agent.create_a2a_transport_server"):
            with patch(
                "examples.agents.controller_agent.BaseA2AAgent.__init__"
            ) as mock_init:
                mock_init.return_value = None
                from examples.agents.controller_agent import ControllerAgent

                _agent = ControllerAgent()

                call_kwargs = mock_init.call_args[1]
                connected = call_kwargs["connected_agents"]
                assert "http://localhost:9001" in connected
                assert "http://localhost:9002" in connected

    def test_init_with_custom_connected_agents(self) -> None:
        """Should accept custom connected agents list."""
        custom_agents = [
            "http://localhost:8001",
            "http://localhost:8002",
            "http://localhost:8003",
        ]

        with patch("examples.agents.controller_agent.create_a2a_transport_server"):
            with patch(
                "examples.agents.controller_agent.BaseA2AAgent.__init__"
            ) as mock_init:
                mock_init.return_value = None
                from examples.agents.controller_agent import ControllerAgent

                _agent = ControllerAgent(connected_agents=custom_agents)

                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["connected_agents"] == custom_agents

    def test_get_skills_returns_coordination_skills(self) -> None:
        """Should return coordination-related skills."""
        with patch("examples.agents.controller_agent.create_a2a_transport_server"):
            with patch(
                "examples.agents.controller_agent.BaseA2AAgent.__init__",
                return_value=None,
            ):
                from examples.agents.controller_agent import ControllerAgent

                agent = ControllerAgent()
                skills = agent._get_skills()

                assert len(skills) == 2
                skill_ids = [s["id"] for s in skills]
                assert "multi_agent_coordination" in skill_ids
                assert "agent_discovery" in skill_ids

    def test_get_allowed_tools_returns_a2a_tools(self) -> None:
        """Should return A2A transport tools with correct naming convention.

        Tool naming follows: mcp__<server_key>__<tool_name>
        Server key = name.lower().replace(" ", "_") = "controller_agent"
        """
        with patch("examples.agents.controller_agent.create_a2a_transport_server"):
            with patch(
                "examples.agents.controller_agent.BaseA2AAgent.__init__",
                return_value=None,
            ):
                from examples.agents.controller_agent import ControllerAgent

                agent = ControllerAgent()
                tools = agent._get_allowed_tools()

                # Tool names use controller_agent as the server key
                assert "mcp__controller_agent__query_agent" in tools
                assert "mcp__controller_agent__discover_agent" in tools


class TestWeatherAgentMain:
    """Tests for weather_agent main function."""

    def test_main_reads_port_from_environment(self) -> None:
        """Should read port from AGENT_PORT environment variable."""
        with patch.dict(os.environ, {"AGENT_PORT": "8888"}):
            with patch(
                "examples.agents.weather_agent.WeatherAgent"
            ) as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.weather_agent import main

                main()

                mock_agent_class.assert_called_with(port=8888)
                mock_agent.run.assert_called_once()

    def test_main_uses_default_port(self) -> None:
        """Should use default port 9001 when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "examples.agents.weather_agent.WeatherAgent"
            ) as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.weather_agent import main

                main()

                mock_agent_class.assert_called_with(port=9001)


class TestMapsAgentMain:
    """Tests for maps_agent main function."""

    def test_main_reads_port_from_environment(self) -> None:
        """Should read port from AGENT_PORT environment variable."""
        with patch.dict(os.environ, {"AGENT_PORT": "7777"}):
            with patch("examples.agents.maps_agent.MapsAgent") as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.maps_agent import main

                main()

                mock_agent_class.assert_called_with(port=7777)

    def test_main_uses_default_port(self) -> None:
        """Should use default port 9002 when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("examples.agents.maps_agent.MapsAgent") as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.maps_agent import main

                main()

                mock_agent_class.assert_called_with(port=9002)


class TestControllerAgentMain:
    """Tests for controller_agent main function."""

    def test_main_reads_port_from_environment(self) -> None:
        """Should read port from AGENT_PORT environment variable."""
        with patch.dict(os.environ, {"AGENT_PORT": "6666"}, clear=True):
            with patch(
                "examples.agents.controller_agent.ControllerAgent"
            ) as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.controller_agent import main

                main()

                mock_agent_class.assert_called()
                call_kwargs = mock_agent_class.call_args[1]
                assert call_kwargs["port"] == 6666

    def test_main_parses_connected_agents_from_env(self) -> None:
        """Should parse CONNECTED_AGENTS from environment."""
        with patch.dict(
            os.environ,
            {
                "AGENT_PORT": "9000",
                "CONNECTED_AGENTS": "http://host1:8001, http://host2:8002",
            },
        ):
            with patch(
                "examples.agents.controller_agent.ControllerAgent"
            ) as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.controller_agent import main

                main()

                call_kwargs = mock_agent_class.call_args[1]
                connected = call_kwargs["connected_agents"]
                assert "http://host1:8001" in connected
                assert "http://host2:8002" in connected

    def test_main_uses_default_connected_agents(self) -> None:
        """Should use None (defaults) when CONNECTED_AGENTS not set."""
        with patch.dict(os.environ, {"AGENT_PORT": "9000"}, clear=True):
            with patch(
                "examples.agents.controller_agent.ControllerAgent"
            ) as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent_class.return_value = mock_agent

                from examples.agents.controller_agent import main

                main()

                call_kwargs = mock_agent_class.call_args[1]
                assert call_kwargs.get("connected_agents") is None


class TestAgentSkillStructure:
    """Tests for agent skill data structure consistency."""

    def test_all_skills_have_required_fields(self) -> None:
        """All skills should have id, name, description, tags, examples."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
                with patch(
                    "examples.agents.controller_agent.create_a2a_transport_server"
                ):
                    with patch(
                        "examples.agents.weather_agent.BaseA2AAgent.__init__",
                        return_value=None,
                    ):
                        with patch(
                            "examples.agents.maps_agent.BaseA2AAgent.__init__",
                            return_value=None,
                        ):
                            with patch(
                                "examples.agents.controller_agent.BaseA2AAgent.__init__",
                                return_value=None,
                            ):
                                from examples.agents.controller_agent import (
                                    ControllerAgent,
                                )
                                from examples.agents.maps_agent import MapsAgent
                                from examples.agents.weather_agent import WeatherAgent

                                agents = [
                                    WeatherAgent(),
                                    MapsAgent(),
                                    ControllerAgent(),
                                ]
                                required_fields = [
                                    "id",
                                    "name",
                                    "description",
                                    "tags",
                                    "examples",
                                ]

                                for agent in agents:
                                    for skill in agent._get_skills():
                                        for field in required_fields:
                                            assert field in skill, (
                                                f"Missing {field} in {agent.__class__.__name__}"
                                            )

    def test_skill_ids_are_unique_per_agent(self) -> None:
        """Skill IDs should be unique within each agent."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
                with patch(
                    "examples.agents.controller_agent.create_a2a_transport_server"
                ):
                    with patch(
                        "examples.agents.weather_agent.BaseA2AAgent.__init__",
                        return_value=None,
                    ):
                        with patch(
                            "examples.agents.maps_agent.BaseA2AAgent.__init__",
                            return_value=None,
                        ):
                            with patch(
                                "examples.agents.controller_agent.BaseA2AAgent.__init__",
                                return_value=None,
                            ):
                                from examples.agents.controller_agent import (
                                    ControllerAgent,
                                )
                                from examples.agents.maps_agent import MapsAgent
                                from examples.agents.weather_agent import WeatherAgent

                                agents = [
                                    WeatherAgent(),
                                    MapsAgent(),
                                    ControllerAgent(),
                                ]

                                for agent in agents:
                                    skills = agent._get_skills()
                                    ids = [s["id"] for s in skills]
                                    assert len(ids) == len(set(ids)), (
                                        f"Duplicate IDs in {agent.__class__.__name__}"
                                    )


class TestAgentToolNaming:
    """Tests for MCP tool naming conventions."""

    def test_tool_names_follow_convention(self) -> None:
        """Tool names should follow mcp__<server>__<tool> pattern."""
        with patch("examples.agents.weather_agent.create_sdk_mcp_server"):
            with patch("examples.agents.maps_agent.create_sdk_mcp_server"):
                with patch(
                    "examples.agents.controller_agent.create_a2a_transport_server"
                ):
                    with patch(
                        "examples.agents.weather_agent.BaseA2AAgent.__init__",
                        return_value=None,
                    ):
                        with patch(
                            "examples.agents.maps_agent.BaseA2AAgent.__init__",
                            return_value=None,
                        ):
                            with patch(
                                "examples.agents.controller_agent.BaseA2AAgent.__init__",
                                return_value=None,
                            ):
                                from examples.agents.controller_agent import (
                                    ControllerAgent,
                                )
                                from examples.agents.maps_agent import MapsAgent
                                from examples.agents.weather_agent import WeatherAgent

                                agents = [
                                    WeatherAgent(),
                                    MapsAgent(),
                                    ControllerAgent(),
                                ]

                                for agent in agents:
                                    for tool in agent._get_allowed_tools():
                                        assert tool.startswith("mcp__"), (
                                            f"Tool {tool} doesn't follow naming convention"
                                        )
                                        parts = tool.split("__")
                                        assert len(parts) == 3, (
                                            f"Tool {tool} has wrong number of parts"
                                        )
