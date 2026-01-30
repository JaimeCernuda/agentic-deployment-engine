"""Maps Agent using claude-code-sdk properly with SDK MCP server."""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.maps_tools import get_cities, get_distance
from src import BaseA2AAgent
from src.security import PermissionPreset


class MapsAgent(BaseA2AAgent):
    """Maps Agent that uses SDK MCP server via claude-code-sdk.

    Inherits A2A capabilities and uses claude-code-sdk with in-process
    MCP server for maps/distance functionality.
    """

    def __init__(
        self,
        port: int = 9002,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Create SDK MCP server with maps tools
        # IMPORTANT: Server name must match the dictionary key used in base_a2a_agent.py
        # which is self.name.lower().replace(" ", "_") = "maps_agent"
        maps_sdk_server = create_sdk_mcp_server(
            name="maps_agent", version="1.0.0", tools=[get_distance, get_cities]
        )

        # Custom system prompt for maps agent
        system_prompt = """You are a Maps Agent specialized in providing geographical information and distance calculations.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__maps_agent__get_distance`: Calculate distance between two cities (Tokyo, London, New York, Paris)
- `mcp__maps_agent__get_cities`: List all available cities

**How to respond to queries:**
1. When asked about distance between cities, call mcp__maps_agent__get_distance with origin and destination
2. When asked what cities are available, call mcp__maps_agent__get_cities
3. Use kilometers by default, miles for US-related queries unless specified
4. Provide helpful travel context and insights

**DO NOT:**
- Try to query yourself or other agents via HTTP/curl
- Use the Bash tool unless necessary for non-maps tasks
- Calculate distances manually - always use the tools"""

        super().__init__(
            name="Maps Agent",
            description="Intelligent maps and distance analysis using SDK MCP tools",
            port=port,
            sdk_mcp_server=maps_sdk_server,
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define maps agent skills for A2A discovery."""
        return [
            {
                "id": "distance_calculation",
                "name": "Distance Calculation",
                "description": "Calculate distances between cities",
                "tags": ["maps", "distance", "travel"],
                "examples": [
                    "How far is Tokyo from London?",
                    "Distance between New York and Paris",
                    "Calculate distance from London to Tokyo",
                ],
            },
            {
                "id": "city_locations",
                "name": "Available Cities",
                "description": "Get list of available cities for distance calculations",
                "tags": ["maps", "cities", "locations"],
                "examples": [
                    "What cities are available?",
                    "List available locations",
                    "Show me available cities",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow Maps SDK MCP tools."""
        # Tool naming: mcp__<server_key>__<tool_name>
        # Server key comes from dict key in base_a2a_agent.py = "maps_agent"
        # Tool names come from @tool decorator = "get_distance", "get_cities"
        return ["mcp__maps_agent__get_distance", "mcp__maps_agent__get_cities"]


def main():
    """Run the Maps Agent."""
    import os

    # Read configuration from environment variables
    port = int(os.getenv("AGENT_PORT", "9002"))

    agent = MapsAgent(port=port)
    print(f"Starting Maps Agent on port {port}...")
    print("Using SDK MCP server with maps tools")
    agent.run()


if __name__ == "__main__":
    main()
