"""Astronomy Agent using external stdio MCP server (FastMCP 2.0).

This agent provides space/astronomy data via an EXTERNAL stdio MCP server,
using FastMCP 2.0. The data is completely different from weather data,
making it easy to verify external MCP integration works correctly.
"""

import os
import sys
from typing import Any

from src import BaseA2AAgent
from src.security import PermissionPreset


class AstronomyStdioAgent(BaseA2AAgent):
    """Astronomy Agent using external stdio MCP server.

    Uses FastMCP 2.0 astronomy server running as a subprocess.
    Returns planet/constellation data that is clearly distinct from weather.
    """

    def __init__(
        self,
        port: int = 9003,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Get Python executable path
        python_path = sys.executable

        # Configure stdio MCP server - FastMCP 2.0
        stdio_mcp_config = {
            "type": "stdio",
            "command": python_path,
            "args": ["-m", "examples.mcp_servers.astronomy_stdio_server"],
            "env": {},
        }

        system_prompt = """You are an Astronomy Agent specialized in space and celestial information.

**IMPORTANT: You have access to these MCP tools from an EXTERNAL stdio server:**
- `mcp__astronomy_stdio__get_planet_info`: Get info about a planet (Mercury, Venus, Earth, Mars, Jupiter)
- `mcp__astronomy_stdio__get_constellation_info`: Get info about a constellation (Orion, Ursa Major, Scorpius)
- `mcp__astronomy_stdio__list_planets`: List all available planets
- `mcp__astronomy_stdio__list_constellations`: List all available constellations

**How to respond:**
1. When asked about a planet, use get_planet_info with the planet name
2. When asked about a constellation, use get_constellation_info
3. When asked what's available, use list_planets or list_constellations

**DO NOT:**
- Guess astronomical data - always use the tools
- Make up information without calling tools
- Provide weather data (that's a different agent!)"""

        super().__init__(
            name="Astronomy Stdio Agent",
            description="Astronomy agent using FastMCP 2.0 external stdio MCP server",
            port=port,
            sdk_mcp_server=None,
            mcp_servers={"astronomy_stdio": stdio_mcp_config},
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define astronomy agent skills for A2A discovery."""
        return [
            {
                "id": "planet_info",
                "name": "Planet Information",
                "description": "Get information about planets in our solar system",
                "tags": ["astronomy", "planets", "space", "stdio", "external"],
                "examples": [
                    "Tell me about Mars",
                    "What are Jupiter's moons?",
                ],
            },
            {
                "id": "constellation_info",
                "name": "Constellation Information",
                "description": "Get information about constellations",
                "tags": ["astronomy", "stars", "constellations", "stdio", "external"],
                "examples": [
                    "Tell me about Orion",
                    "What stars are in Ursa Major?",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow astronomy stdio MCP tools."""
        return [
            "mcp__astronomy_stdio__get_planet_info",
            "mcp__astronomy_stdio__get_constellation_info",
            "mcp__astronomy_stdio__list_planets",
            "mcp__astronomy_stdio__list_constellations",
        ]


def main():
    """Run the Astronomy Stdio Agent."""
    port = int(os.getenv("AGENT_PORT", "9003"))
    agent = AstronomyStdioAgent(port=port)
    print(f"Starting Astronomy Stdio Agent on port {port}...")
    print("Using FastMCP 2.0 external stdio MCP server")
    agent.run()


if __name__ == "__main__":
    main()
