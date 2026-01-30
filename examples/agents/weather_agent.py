"""Weather Agent using claude-code-sdk properly with SDK MCP server."""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.weather_tools import get_locations, get_weather
from src import BaseA2AAgent
from src.security import PermissionPreset


class WeatherAgent(BaseA2AAgent):
    """Weather Agent that uses SDK MCP server via claude-code-sdk.

    Inherits A2A capabilities and uses claude-code-sdk with in-process
    MCP server for weather functionality.
    """

    def __init__(
        self,
        port: int = 9001,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Create SDK MCP server with weather tools
        # IMPORTANT: Server name must match the dictionary key used in base_a2a_agent.py
        # which is self.name.lower().replace(" ", "_") = "weather_agent"
        weather_sdk_server = create_sdk_mcp_server(
            name="weather_agent", version="1.0.0", tools=[get_weather, get_locations]
        )

        # Custom system prompt for weather agent
        system_prompt = """You are a Weather Agent specialized in providing weather information and analysis.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__weather_agent__get_weather`: Get current weather for a city (Tokyo, London, New York, Paris)
- `mcp__weather_agent__get_locations`: List all available cities

**How to respond to queries:**
1. When asked about weather in a specific city, call mcp__weather_agent__get_weather with the city name
2. When asked what cities are available, call mcp__weather_agent__get_locations
3. Use metric units for European cities, imperial for US cities unless specified otherwise
4. Provide helpful, conversational weather insights

**DO NOT:**
- Try to query yourself via HTTP/curl
- Use the Bash tool unless necessary for non-weather tasks
- Guess weather data - always use the tools"""

        super().__init__(
            name="Weather Agent",
            description="Intelligent weather analysis using SDK MCP tools",
            port=port,
            sdk_mcp_server=weather_sdk_server,
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define weather agent skills for A2A discovery."""
        return [
            {
                "id": "weather_analysis",
                "name": "Weather Analysis",
                "description": "Get current weather and intelligent analysis",
                "tags": ["weather", "current"],
                "examples": [
                    "What's the weather in Tokyo?",
                    "How's the weather in London?",
                    "Current conditions in New York",
                ],
            },
            {
                "id": "weather_locations",
                "name": "Weather Locations",
                "description": "Get available weather locations",
                "tags": ["weather", "locations"],
                "examples": [
                    "What weather locations are available?",
                    "List weather cities",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow Weather SDK MCP tools."""
        # Tool naming: mcp__<server_key>__<tool_name>
        # Server key comes from dict key in base_a2a_agent.py = "weather_agent"
        # Tool names come from @tool decorator = "get_weather", "get_locations"
        return ["mcp__weather_agent__get_weather", "mcp__weather_agent__get_locations"]


def main():
    """Run the Weather Agent."""
    import os

    # Read configuration from environment variables
    port = int(os.getenv("AGENT_PORT", "9001"))

    agent = WeatherAgent(port=port)
    print(f"Starting Weather Agent on port {port}...")
    print("Using SDK MCP server with weather tools")
    agent.run()


if __name__ == "__main__":
    main()
